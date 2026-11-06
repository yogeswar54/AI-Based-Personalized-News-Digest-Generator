import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.api.v1 import news as news_api
from app.config import get_settings
from app.database import mongodb as mongo_module
from app.main import app
from app.services.deduplication import duplicate_detection_service as dedup
from app.services.deduplication import news_grouping_service as grouping
from app.services.deduplication.embedding_service import generate_embeddings
from app.services.deduplication.similarity_service import cosine_similarity
from app.services.deduplication.text_preparation import prepare_article_text
from app.services.news import news_collector


def _read(document, path):
    value = document
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            return None, False
        value = value[key]
    return value, True


def _condition(actual, exists, expected):
    if not isinstance(expected, dict):
        return exists and actual == expected
    for operator, value in expected.items():
        if operator == "$exists" and exists != value:
            return False
        if operator == "$ne" and exists and actual == value:
            return False
        if operator == "$nin" and exists and actual in value:
            return False
        if operator == "$in" and ((not exists and None not in value) or (exists and actual not in value)):
            return False
        if operator == "$lt" and (actual is None or actual >= value):
            return False
        if operator == "$gte" and (actual is None or actual < value):
            return False
        if operator == "$lte" and (actual is None or actual > value):
            return False
        if operator == "$regex":
            import re

            flags = re.IGNORECASE if expected.get("$options") == "i" else 0
            values = actual if isinstance(actual, list) else [actual]
            if not any(isinstance(item, str) and re.search(value, item, flags) for item in values):
                return False
    return True


def _matches(document, query):
    for key, expected in query.items():
        if key == "$or":
            if not any(_matches(document, clause) for clause in expected):
                return False
            continue
        if key == "$and":
            if not all(_matches(document, clause) for clause in expected):
                return False
            continue
        actual, exists = _read(document, key)
        if not _condition(actual, exists, expected):
            return False
    return True


def _set_dotted(document, key, value):
    parts = key.split(".")
    target = document
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    target[parts[-1]] = value


class Cursor:
    def __init__(self, documents):
        self.documents = list(documents)

    def sort(self, key, direction=-1):
        self.documents.sort(key=lambda doc: _read(doc, key)[0] or datetime.min.replace(tzinfo=timezone.utc), reverse=direction < 0)
        return self

    def skip(self, count):
        self.documents = self.documents[count:]
        return self

    def limit(self, count):
        self.documents = self.documents[:count]
        return self

    def __iter__(self):
        return iter(self.documents)


class Collection:
    def __init__(self):
        self.documents = []

    def create_index(self, *args, **kwargs):
        return None

    def insert_one(self, document):
        document.setdefault("_id", ObjectId())
        self.documents.append(document)
        return SimpleNamespace(inserted_id=document["_id"])

    def find_one(self, query):
        return next((doc for doc in self.documents if _matches(doc, query)), None)

    def find(self, query=None, projection=None):
        return Cursor(doc for doc in self.documents if _matches(doc, query or {}))

    def update_one(self, query, update):
        for document in self.documents:
            if not _matches(document, query):
                continue
            for key, value in update.get("$set", {}).items():
                _set_dotted(document, key, value)
            for key, value in update.get("$addToSet", {}).items():
                items = document.setdefault(key, [])
                if value not in items:
                    items.append(value)
            for key, value in update.get("$pull", {}).items():
                document[key] = [item for item in document.get(key, []) if item != value]
            for key in update.get("$unset", {}):
                document.pop(key, None)
            return SimpleNamespace(modified_count=1, matched_count=1)
        return SimpleNamespace(modified_count=0, matched_count=0)

    def count_documents(self, query=None):
        return sum(1 for doc in self.documents if _matches(doc, query or {}))

    def delete_one(self, query):
        for index, document in enumerate(self.documents):
            if _matches(document, query):
                self.documents.pop(index)
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)


class Database:
    def __init__(self):
        self.collections = {
            "news_articles": Collection(),
            "news_event_groups": Collection(),
        }

    def __getitem__(self, name):
        return self.collections[name]


def patch_database(monkeypatch, articles=()):
    database = Database()
    for article in articles:
        database["news_articles"].insert_one(article)
    monkeypatch.setattr(mongo_module, "get_database", lambda: database)
    monkeypatch.setattr(dedup, "get_database", lambda: database)
    monkeypatch.setattr(grouping, "get_database", lambda: database)
    monkeypatch.setattr(news_collector, "get_database", lambda: database)
    monkeypatch.setattr(news_collector, "get_news_collection", lambda: database["news_articles"])
    monkeypatch.setattr(news_api, "get_news_collection", lambda: database["news_articles"])
    return database


def make_article(title, description="", *, article_id=None, category="Technology", days_ago=0, **extra):
    article = {
        "_id": article_id or ObjectId(),
        "title": title,
        "processed_title": title,
        "description": description,
        "processed_description": description,
        "content": "",
        "keywords": [],
        "category": category,
        "source": {"name": "Example Publisher", "url": ""},
        "url": f"https://example.com/{article_id or ObjectId()}",
        "canonical_url": f"https://example.com/{article_id or ObjectId()}",
        "provider": "rss",
        "external_id": str(article_id or ObjectId()),
        "published_at": datetime.now(timezone.utc) - timedelta(days=days_ago),
        "preprocessing_status": "completed",
        "embedding_status": "pending",
        "duplicate_detection_status": "pending",
    }
    article.update(extra)
    return article


def test_text_preparation_combines_and_deduplicates_cleaned_text():
    text = prepare_article_text({
        "processed_title": "<b>OpenAI launches a model</b>",
        "title": "Ignored source title",
        "processed_description": "OpenAI launches a model",
        "content": "The company announced its system.",
    })
    assert text == "OpenAI launches a model The company announced its system."


@pytest.mark.parametrize(
    "article",
    [
        {"title": "", "description": ""},
        {"title": None, "description": None},
        {"title": "<p></p>", "description": "  "},
    ],
)
def test_text_preparation_returns_empty_for_missing_article_text(article):
    assert prepare_article_text(article) == ""


def test_embedding_generation_reuses_model_and_supports_batches(monkeypatch):
    calls = []

    class Model:
        def encode(self, texts, **kwargs):
            calls.append((texts, kwargs))
            return [[1.0, 0.0], [0.0, 1.0]]

    monkeypatch.setattr("app.services.deduplication.embedding_service._load_model", lambda name: Model())
    vectors = generate_embeddings(["first story", "second story"])
    assert vectors == [[1.0, 0.0], [0.0, 1.0]]
    assert len(calls) == 1
    assert calls[0][1]["normalize_embeddings"] is True
    assert calls[0][1]["show_progress_bar"] is False


@pytest.mark.parametrize("texts", [[], ["  "]])
def test_embedding_generation_handles_empty_batch_and_rejects_empty_text(texts):
    if not texts:
        assert generate_embeddings(texts) == []
    else:
        with pytest.raises(ValueError):
            generate_embeddings(texts)


def test_cosine_similarity_handles_positive_opposite_zero_and_invalid_vectors():
    assert cosine_similarity([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine_similarity([1, 0], [-1, 0]) == pytest.approx(-1.0)
    assert cosine_similarity([0, 0], [1, 0]) == 0.0
    with pytest.raises(ValueError, match="dimensions"):
        cosine_similarity([1], [1, 2])
    with pytest.raises(ValueError, match="finite"):
        cosine_similarity([float("nan")], [1])
    with pytest.raises(ValueError, match="numeric"):
        cosine_similarity(["bad"], [1])


def test_categories_and_event_context_prevent_unrelated_matches():
    first = make_article("OpenAI launches an AI model", "The model was announced today.")
    same_event = make_article("OpenAI introduces a new AI model", "The company revealed a model today.")
    different_category = make_article("OpenAI introduces a new AI model", category="Sports")
    different_event = make_article("OpenAI opens new European office", "The company plans to hire staff.")

    assert grouping.has_event_context_match(first, same_event)
    assert not grouping.has_event_context_match(first, different_category)
    assert not grouping.has_strong_event_context(first, different_event)


def test_find_best_group_match_requires_similarity_and_context(monkeypatch):
    monkeypatch.setattr(
        "app.services.deduplication.news_grouping_service.get_settings",
        lambda: SimpleNamespace(news_similarity_threshold=0.75, news_duplicate_threshold=0.85),
    )
    source = make_article("OpenAI launches a new AI model")
    candidate = make_article(
        "OpenAI introduces a new AI model",
        embedding=[1.0, 0.0],
        embedding_model="model-a",
    )
    source.update({"embedding": [1.0, 0.0], "embedding_model": "model-a"})
    assert grouping.find_best_group_match(source, [candidate])["similarity"] == pytest.approx(1.0)
    candidate["embedding"] = [0.0, 1.0]
    assert grouping.find_best_group_match(source, [candidate]) is None


def test_exact_duplicate_detection_uses_url_and_provider_id_but_not_domain(monkeypatch):
    database = patch_database(monkeypatch)
    original = make_article("Original report")
    database["news_articles"].insert_one(original)
    identical_url = make_article("Different headline", url=original["url"], canonical_url=original["canonical_url"])
    same_domain = make_article("Another report", url="https://example.com/a-different-story", canonical_url="https://example.com/a-different-story")
    same_provider_id = make_article("Same provider ID", provider=original["provider"], external_id=original["external_id"])

    assert dedup._find_exact_duplicate(database["news_articles"], identical_url)["_id"] == original["_id"]
    assert dedup._find_exact_duplicate(database["news_articles"], same_provider_id)["_id"] == original["_id"]
    assert dedup._find_exact_duplicate(database["news_articles"], same_domain) is None


def test_detect_duplicates_creates_new_group_and_stores_embedding(monkeypatch):
    article = make_article("OpenAI launches a new AI model", "The company made an announcement.")
    database = patch_database(monkeypatch, [article])
    monkeypatch.setattr(dedup, "generate_embeddings", lambda texts: [[1.0, 0.0] for _ in texts])

    result = asyncio.run(dedup.detect_duplicates_for_article(article))

    stored = database["news_articles"].find_one({"_id": article["_id"]})
    groups = database["news_event_groups"].documents
    assert result["status"] == "unmatched"
    assert stored["embedding_status"] == "completed"
    assert stored["duplicate_detection_status"] == "completed"
    assert stored["event_group_id"] == groups[0]["_id"]
    assert groups[0]["article_count"] == 1


def test_existing_event_group_is_extended_once_and_representative_updated(monkeypatch):
    first = make_article("OpenAI launches an AI model", "Full report content.", content="Full article body.")
    second = make_article(
        "OpenAI introduces its new AI model",
        "A short report from another publisher.",
        embedding=[1.0, 0.0],
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
    )
    database = patch_database(monkeypatch, [first, second])
    monkeypatch.setattr(dedup, "generate_embeddings", lambda texts: [[1.0, 0.0] for _ in texts])
    group_id = grouping.create_event_group(first)
    database["news_articles"].update_one(
        {"_id": first["_id"]},
        {"$set": {
            "embedding": [1.0, 0.0],
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "embedding_status": "completed",
        }},
    )
    result = asyncio.run(dedup.detect_duplicates_for_article(second))

    group = database["news_event_groups"].find_one({"_id": group_id})
    assert result["status"] == "grouped"
    assert group["article_count"] == 2
    assert group["article_ids"].count(second["_id"]) == 1
    assert database["news_articles"].find_one({"_id": second["_id"]})["event_group_id"] == group_id


def test_representative_selection_prefers_complete_summarized_article():
    earlier = make_article("Earlier report", content="Full details.", published_at=datetime.now(timezone.utc) - timedelta(days=1))
    better = make_article(
        "Better report",
        description="A clear description",
        summarization={"status": "completed"},
        published_at=datetime.now(timezone.utc),
    )
    assert grouping.select_representative_article([earlier, better]) is better


def test_failed_embedding_batch_can_be_retried(monkeypatch):
    article = make_article("An eligible technology story")
    database = patch_database(monkeypatch, [article])
    monkeypatch.setattr(dedup, "generate_embeddings", lambda texts: (_ for _ in ()).throw(RuntimeError("model failure")))

    first = asyncio.run(dedup.process_pending_articles(batch_size=10))
    assert first["failed"] == 1
    assert database["news_articles"].documents[0]["embedding_status"] == "failed"

    monkeypatch.setattr(dedup, "generate_embeddings", lambda texts: [[1.0, 0.0] for _ in texts])
    retried = asyncio.run(dedup.process_pending_articles(batch_size=10, retry_failed=True))
    assert retried["unmatched"] == 1
    assert database["news_articles"].documents[0]["embedding_status"] == "completed"


def test_deduplication_stats_requires_admin_and_reports_counts(monkeypatch):
    article = make_article("One story", embedding=[1.0], embedding_status="completed")
    ungrouped_article = make_article("Another story")
    database = patch_database(monkeypatch, [article, ungrouped_article])
    database["news_event_groups"].insert_one({
        "_id": ObjectId(),
        "event_title": "A story",
        "representative_article_id": article["_id"],
        "article_ids": [article["_id"]],
        "article_count": 1,
        "category": "Technology",
        "keywords": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    database["news_articles"].update_one(
        {"_id": article["_id"]},
        {"$set": {"event_group_id": database["news_event_groups"].documents[0]["_id"]}},
    )
    with TestClient(app) as client:
        denied = client.get("/api/v1/admin/news/deduplication/stats")
        allowed = client.get(
            "/api/v1/admin/news/deduplication/stats",
            headers={"X-Admin-Key": "development-admin-key"},
        )
    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json()["articles_with_embeddings"] == 1
    assert allowed.json()["total_event_groups"] == 1
    assert allowed.json()["articles_assigned_to_groups"] == 1
    assert allowed.json()["articles_not_yet_grouped"] == 1


def test_event_group_and_related_article_apis(monkeypatch):
    first = make_article("OpenAI launches a model", "First publisher report", embedding=[1.0, 0.0])
    second = make_article("OpenAI launches a model", "Second publisher report", embedding=[1.0, 0.0])
    database = patch_database(monkeypatch, [first, second])
    group_id = grouping.create_event_group(first)
    grouping.attach_article_to_group(second, group_id)

    with TestClient(app) as client:
        groups_response = client.get("/api/v1/news/groups")
        group_response = client.get(f"/api/v1/news/groups/{group_id}")
        related_response = client.get(f"/api/v1/news/{first['_id']}/related")

    assert groups_response.status_code == 200
    assert groups_response.json()["items"][0]["article_count"] == 2
    assert group_response.status_code == 200
    assert len(group_response.json()["articles"]) == 2
    assert related_response.status_code == 200
    assert len(related_response.json()["items"]) == 1
    assert related_response.json()["items"][0]["similarity"] == pytest.approx(1.0)
    assert "embedding" not in related_response.json()["items"][0]["article"]
