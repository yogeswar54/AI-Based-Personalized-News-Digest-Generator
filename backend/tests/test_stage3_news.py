import asyncio
import os
from datetime import datetime, timezone

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("DATABASE_NAME", "personalized_news_digest_test")

from bson import ObjectId
from fastapi.testclient import TestClient

from app.database import mongodb as mongo_module
from app.main import app
from app.services.news.news_collector import _matches_duplicate, _update_existing_article, collect_news
from app.services.news.news_normalizer import normalize_article
from app.services.news import news_collector, rss_provider


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents
        self._sorted = False

    def sort(self, key, direction=-1):
        self.documents = sorted(
            self.documents,
            key=lambda item: item.get(key, datetime.min.replace(tzinfo=timezone.utc)),
            reverse=direction == -1,
        )
        self._sorted = True
        return self

    def skip(self, count):
        self.documents = self.documents[count:]
        return self

    def limit(self, count):
        self.documents = self.documents[:count]
        return self

    def __iter__(self):
        return iter(self.documents)

    def __len__(self):
        return len(self.documents)


class FakeCollection:
    def __init__(self):
        self.documents = []

    def create_index(self, *args, **kwargs):
        return None

    def insert_one(self, document):
        document.setdefault("_id", ObjectId())
        self.documents.append(document)
        return type("InsertResult", (), {"inserted_id": document["_id"]})()

    def update_one(self, query, update):
        for document in self.documents:
            if document.get("_id") == query.get("_id"):
                document.update(update.get("$set", {}))
                return None
        return None

    def find_one(self, query):
        if "$or" in query:
            for document in self.documents:
                for condition in query["$or"]:
                    if "canonical_url" in condition and document.get("canonical_url") == condition["canonical_url"]:
                        return document
                    if (
                        "provider" in condition
                        and "external_id" in condition
                        and document.get("provider") == condition["provider"]
                        and document.get("external_id") == condition["external_id"]
                    ):
                        return document
            return None
        if "_id" in query:
            for document in self.documents:
                if document.get("_id") == query["_id"]:
                    return document
            return None
        return None

    def find(self, query=None, projection=None):
        query = query or {}
        result = []
        for document in self.documents:
            if not query:
                result.append(document)
                continue
            if query.get("$or"):
                match = False
                for condition in query["$or"]:
                    if "title" in condition and document.get("title") and condition["title"].get("$regex") in document["title"]:
                        match = True
                        break
                    if "description" in condition and document.get("description") and condition["description"].get("$regex") in document["description"]:
                        match = True
                        break
                    if "content" in condition and document.get("content") and condition["content"].get("$regex") in document["content"]:
                        match = True
                        break
                if match:
                    result.append(document)
                continue
            if "category" in query and document.get("category") != query["category"]:
                continue
            if "source.name" in query and document.get("source", {}).get("name") != query["source.name"]:
                continue
            if "country" in query and document.get("country") != query["country"]:
                continue
            if "language" in query and document.get("language") != query["language"]:
                continue
            if "published_at" in query:
                published = document.get("published_at")
                if isinstance(published, datetime):
                    min_date = query["published_at"].get("$gte")
                    max_date = query["published_at"].get("$lte")
                    if min_date and published < min_date:
                        continue
                    if max_date and published > max_date:
                        continue
            result.append(document)
        return FakeCursor(result)

    def count_documents(self, query=None):
        query = query or {}
        return len(list(self.find(query)))

    def distinct(self, field):
        if field == "source.name":
            return [document.get("source", {}).get("name") for document in self.documents if document.get("source", {}).get("name")]
        return [document.get(field) for document in self.documents if document.get(field)]


class FakeDatabase:
    def __getitem__(self, name):
        if name == "news_articles":
            if not hasattr(self, "articles"):
                self.articles = FakeCollection()
            return self.articles
        if name == "news_collection_logs":
            if not hasattr(self, "logs"):
                self.logs = FakeCollection()
            return self.logs
        raise KeyError(name)


def patch_fake_database(monkeypatch):
    fake_db = FakeDatabase()
    monkeypatch.setattr(mongo_module, "get_database", lambda: fake_db)
    monkeypatch.setattr("app.services.news.news_collector.get_database", lambda: fake_db)
    monkeypatch.setattr("app.services.news.news_collector.get_news_logs_collection", lambda: fake_db["news_collection_logs"])
    monkeypatch.setattr("app.api.v1.news.get_news_collection", lambda: fake_db["news_articles"])
    return fake_db


def test_news_normalizer_rejects_missing_required_fields():
    assert normalize_article({"title": "Missing URL", "source": {"name": "Example"}}, "rss") is None
    assert normalize_article({"url": "https://example.com/news", "source": {"name": "Example"}}, "rss") is None
    assert normalize_article({"title": "Unsafe URL", "url": "javascript:alert(1)"}, "rss") is None


def test_rss_provider_async_fetch_maps_feed_entries(monkeypatch):
    class FakeResponse:
        status_code = 200
        content = b"""<?xml version="1.0"?><rss version="2.0"><channel>
        <title>Example Feed</title><link>https://example.com</link>
        <item><title>Technology update</title><link>https://example.com/news</link>
        <description>News description</description></item>
        </channel></rss>"""

        def raise_for_status(self):
            return None

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def get(self, url, **kwargs):
            assert url == "https://example.com/feed.xml"
            return FakeResponse()

    monkeypatch.setattr(
        rss_provider,
        "get_settings",
        lambda: type("Settings", (), {
            "rss_feed_urls": ["https://example.com/feed.xml"],
            "news_api_default_country": "us",
        })(),
    )
    monkeypatch.setattr(rss_provider.httpx, "AsyncClient", lambda **_: FakeClient())

    articles = asyncio.run(rss_provider.RSSProvider().fetch_articles())

    assert len(articles) == 1
    assert articles[0]["title"] == "Technology update"
    assert articles[0]["source_name"] == "Example Feed"


def test_provider_retries_transient_http_responses():
    import httpx

    class FakeResponse:
        def __init__(self, status_code):
            self.status_code = status_code
            self.request = httpx.Request("GET", "https://example.test/feed")

        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    "upstream failure",
                    request=self.request,
                    response=httpx.Response(self.status_code, request=self.request),
                )

    class FakeClient:
        def __init__(self):
            self.responses = [FakeResponse(503), FakeResponse(200)]
            self.calls = 0

        async def get(self, url, **kwargs):
            self.calls += 1
            return self.responses.pop(0)

    provider = rss_provider.RSSProvider()
    client = FakeClient()
    response = asyncio.run(provider.get_with_retries(client, "https://example.test/feed"))

    assert response.status_code == 200
    assert client.calls == 2


def test_news_api_sends_key_in_header_and_not_url(monkeypatch):
    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"articles": []}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def get(self, url, *, params=None, headers=None):
            assert "top-headlines" in url
            assert "news-secret" not in url
            assert params is not None and "apiKey" not in params
            assert headers == {"X-Api-Key": "news-secret"}
            return FakeResponse()

    from app.services.news import news_api_provider

    monkeypatch.setattr(
        news_api_provider,
        "get_settings",
        lambda: type("Settings", (), {
            "news_api_key": "news-secret",
            "news_api_default_language": "en",
            "news_api_base_url": "https://news.example/api",
        })(),
    )
    monkeypatch.setattr(news_api_provider.httpx, "AsyncClient", lambda **_: FakeClient())

    assert asyncio.run(news_api_provider.NewsApiProvider().fetch_articles()) == []


def test_collection_counts_unexpected_database_write_errors_as_failures(monkeypatch):
    database = patch_fake_database(monkeypatch)
    article = {
        "title": "Market update",
        "url": "https://example.com/market",
        "source": {"name": "Market Wire"},
    }

    async def news_fetch(self, **kwargs):
        return [article]

    async def rss_fetch(self, **kwargs):
        return []

    def fail_insert(document):
        raise RuntimeError("database write failed")

    monkeypatch.setattr(news_collector.NewsApiProvider, "fetch_articles", news_fetch)
    monkeypatch.setattr(news_collector.RSSProvider, "fetch_articles", rss_fetch)
    monkeypatch.setattr(database["news_articles"], "insert_one", fail_insert)

    report = asyncio.run(collect_news())

    assert report["new_articles"] == 0
    assert report["duplicates_skipped"] == 0
    assert report["failed_articles"] == 1


def test_duplicate_detection_matches_canonical_url(monkeypatch):
    fake_db = patch_fake_database(monkeypatch)
    article = normalize_article(
        {
            "title": "AI News",
            "url": "https://example.com/news?id=5",
            "source": {"name": "Example News"},
            "published_at": "2024-02-01T10:00:00Z",
        },
        "news_api",
    )
    fake_db["news_articles"].insert_one(article)
    duplicate = normalize_article(
        {
            "title": "AI News",
            "url": "https://example.com/news?id=5",
            "source": {"name": "Example News"},
            "published_at": "2024-02-01T11:00:00Z",
        },
        "rss",
    )
    assert _matches_duplicate(fake_db["news_articles"], duplicate)["canonical_url"] == article["canonical_url"]


def test_duplicate_refresh_preserves_completed_preprocessing(monkeypatch):
    fake_db = patch_fake_database(monkeypatch)
    article_id = ObjectId()
    existing = {
        "_id": article_id,
        "title": "AI software report",
        "description": "A technology report.",
        "content": "Detailed technology reporting.",
        "provider_category": "technology",
        "category": "Artificial Intelligence",
        "preprocessing_status": "completed",
        "classification_method": "ai",
        "processed_title": "AI software report",
        "keywords": ["artificial", "intelligence"],
        "summarization": {"status": "completed", "short_summary": "An old summary"},
    }
    fake_db["news_articles"].insert_one(existing)
    refreshed = normalize_article(
        {
            "title": existing["title"],
            "description": existing["description"],
            "content": existing["content"],
            "url": "https://example.com/ai-report",
            "source": {"name": "Example News"},
            "category": "technology",
        },
        "rss",
    )

    assert _update_existing_article(fake_db["news_articles"], existing, refreshed)
    assert existing["preprocessing_status"] == "completed"
    assert existing["category"] == "Artificial Intelligence"
    assert existing["classification_method"] == "ai"
    assert existing["summarization"]["status"] == "completed"
    assert existing["summarization"]["short_summary"] == "An old summary"


def test_duplicate_refresh_resets_preprocessing_when_source_content_changes(monkeypatch):
    fake_db = patch_fake_database(monkeypatch)
    article_id = ObjectId()
    existing = {
        "_id": article_id,
        "title": "AI software report",
        "description": "An old technology report.",
        "content": "Old content.",
        "provider_category": "technology",
        "category": "Artificial Intelligence",
        "preprocessing_status": "completed",
        "classification_method": "ai",
        "processed_title": "AI software report",
        "keywords": ["artificial", "intelligence"],
    }
    fake_db["news_articles"].insert_one(existing)
    refreshed = normalize_article(
        {
            "title": existing["title"],
            "description": "An updated technology report.",
            "content": "Updated content.",
            "url": "https://example.com/ai-report",
            "source": {"name": "Example News"},
            "category": "technology",
        },
        "rss",
    )

    assert _update_existing_article(fake_db["news_articles"], existing, refreshed)
    assert existing["preprocessing_status"] == "pending"
    assert existing["category"] == "Technology"
    assert existing["classification_method"] is None
    assert existing["keywords"] == []
    assert existing["summarization"]["status"] == "pending"
    assert existing["summarization"]["short_summary"] is None


def test_news_endpoints_return_items_and_sources(monkeypatch):
    fake_db = patch_fake_database(monkeypatch)
    fake_db["news_articles"].insert_one(
        {
            "_id": ObjectId(),
            "title": "Tech market update",
            "description": "A fast-moving technology story.",
            "content": "Detailed article content.",
            "url": "https://example.com/tech",
            "canonical_url": "https://example.com/tech",
            "image_url": "https://example.com/image.jpg",
            "source": {"name": "Example News", "url": "https://example.com"},
            "author": "Jane Reporter",
            "provider": "news_api",
            "provider_category": "technology",
            "category": "Technology",
            "language": "en",
            "country": "us",
            "published_at": datetime.now(timezone.utc),
            "collected_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )

    with TestClient(app) as client:
        news_response = client.get("/api/v1/news?page=1&limit=10")
        categories_response = client.get("/api/v1/news/categories")
        sources_response = client.get("/api/v1/news/sources")

    assert news_response.status_code == 200
    assert news_response.json()["items"][0]["category"] == "Technology"
    assert "Technology" in categories_response.json()["categories"]
    assert "Example News" in sources_response.json()["sources"]


def test_admin_collection_requires_secret_key(monkeypatch):
    patch_fake_database(monkeypatch)
    with TestClient(app) as client:
        response = client.post("/api/v1/admin/news/collect")
    assert response.status_code == 403


def test_collect_news_reports_results(monkeypatch):
    patch_fake_database(monkeypatch)
    article = {
        "title": "Market update",
        "url": "https://example.com/market",
        "source": {"name": "Market Wire"},
        "published_at": "2024-04-01T00:00:00Z",
    }

    async def run_collection():
        return await collect_news()

    report = asyncio.run(run_collection())
    assert report["status"] == "success"
    assert isinstance(report["providers_processed"], int)
