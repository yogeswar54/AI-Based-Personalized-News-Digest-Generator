from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
import httpx
from pymongo.errors import DuplicateKeyError

from app.api.v1 import news as news_api
from app.config import Settings
from app.core.dependencies import get_current_user
from app.database import mongodb as mongo_module
from app.main import app
from app.schemas.digest import DigestSettings
from app.services.digest import digest_service as digest
from app.services.recommendation import recommendation_service as recommendations
from app.services.recommendation import diversity_service
from app.services.recommendation.relevance_scorer import score_article
from app.services.recommendation.ranking_service import rank_articles
from app.services import user_service


def _read(document, path):
    value = document
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            return None, False
        value = value[key]
    return value, True


def _matches(document, query):
    for key, expected in query.items():
        if key == "$or":
            if not any(_matches(document, option) for option in expected):
                return False
            continue
        actual, exists = _read(document, key)
        if not isinstance(expected, dict):
            if not exists or actual != expected:
                return False
            continue
        for operator, value in expected.items():
            if operator == "$exists" and exists != value:
                return False
            if operator == "$ne" and exists and actual == value:
                return False
            if operator == "$gte" and (not exists or actual < value):
                return False
            if operator == "$gt" and (not exists or actual <= value):
                return False
            if operator == "$gt" and (not exists or actual <= value):
                return False
            if operator == "$lte" and (not exists or actual > value):
                return False
            if operator == "$lt" and (not exists or actual >= value):
                return False
            if operator == "$in" and ((not exists and None not in value) or (exists and actual not in value)):
                return False
    return True


def _set_path(document, path, value):
    parts = path.split(".")
    target = document
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    target[parts[-1]] = value


class Cursor:
    def __init__(self, documents):
        self.documents = list(documents)

    def sort(self, key, direction=-1):
        fields = key if isinstance(key, list) else [(key, direction)]
        for field, order in reversed(fields):
            self.documents.sort(
                key=lambda document: (_read(document, field)[0] is not None, _read(document, field)[0]),
                reverse=order < 0,
            )
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

    def find_one(self, query, projection=None):
        return next((document for document in self.documents if _matches(document, query)), None)

    def find(self, query=None, projection=None):
        return Cursor(document for document in self.documents if _matches(document, query or {}))

    def update_one(self, query, update, upsert=False):
        document = self.find_one(query)
        if not document:
            if upsert:
                document = {"_id": query.get("_id")}
                for key, value in update.get("$set", {}).items():
                    _set_path(document, key, value)
                self.documents.append(document)
                return SimpleNamespace(matched_count=0, modified_count=0, upserted_id=document["_id"])
            return SimpleNamespace(matched_count=0, modified_count=0)
        for key, value in update.get("$set", {}).items():
            _set_path(document, key, value)
        for key in update.get("$unset", {}):
            document.pop(key, None)
        return SimpleNamespace(matched_count=1, modified_count=1)

    def find_one_and_update(self, query, update, upsert=False, return_document=None):
        document = self.find_one(query)
        if document is None and upsert:
            if any(item.get("_id") == query.get("_id") for item in self.documents):
                raise DuplicateKeyError("active claim")
            document = {"_id": query.get("_id")}
            for key, value in update.get("$set", {}).items():
                _set_path(document, key, value)
            self.documents.append(document)
            return document
        if document:
            for key, value in update.get("$set", {}).items():
                _set_path(document, key, value)
        return document

    def count_documents(self, query=None):
        return sum(_matches(document, query or {}) for document in self.documents)

    def delete_one(self, query):
        for index, document in enumerate(self.documents):
            if _matches(document, query):
                self.documents.pop(index)
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)


class Database:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        return self.collections.setdefault(name, Collection())


def patch_database(monkeypatch, *, users=(), articles=(), groups=()):
    database = Database()
    for collection_name, documents in (
        ("users", users),
        ("news_articles", articles),
        ("news_event_groups", groups),
    ):
        for document in documents:
            database[collection_name].insert_one(document)
    monkeypatch.setattr(mongo_module, "get_database", lambda: database)
    monkeypatch.setattr(user_service, "get_database", lambda: database)
    monkeypatch.setattr(digest, "get_database", lambda: database)
    monkeypatch.setattr(recommendations, "get_database", lambda: database)
    monkeypatch.setattr(news_api, "get_news_collection", lambda: database["news_articles"])
    return database


def make_article(title, category, *, days_ago=0, article_id=None, group_id=None, **extra):
    article = {
        "_id": article_id or ObjectId(),
        "title": title,
        "processed_title": title,
        "description": f"Reporting on {title.lower()}",
        "processed_description": f"Reporting on {title.lower()}",
        "content": "",
        "url": f"https://news.example/{ObjectId()}",
        "canonical_url": f"https://news.example/{ObjectId()}",
        "source": {"name": "News publisher", "url": ""},
        "category": category,
        "keywords": [],
        "published_at": datetime.now(timezone.utc) - timedelta(days=days_ago),
        "preprocessing_status": "completed",
        "summarization": {"status": "pending"},
        "event_group_id": group_id,
    }
    article.update(extra)
    return article


def make_user(*, interests=None, user_id=None, digest_settings=None):
    return {
        "_id": user_id or ObjectId(),
        "email": "reader@example.test",
        "full_name": "Reader",
        "interests": interests if interests is not None else ["Technology"],
        "digest_settings": digest_settings or {},
    }


def test_settings_validate_digest_time_and_iana_timezone():
    assert DigestSettings(timezone="Asia/Kolkata", digest_time="08:30").timezone == "Asia/Kolkata"
    with pytest.raises(ValueError):
        DigestSettings(timezone="Mars/Olympus")
    with pytest.raises(ValueError):
        DigestSettings(digest_time="8am")
    with pytest.raises(ValueError):
        DigestSettings(articles_per_digest=51)


def test_production_settings_reject_development_security_defaults():
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(
            _env_file=None,
            app_env="production",
            cookie_secure=True,
        )
    with pytest.raises(ValueError, match="COOKIE_SECURE"):
        Settings(
            _env_file=None,
            app_env="staging",
            secret_key="s" * 40,
            admin_secret_key="a" * 40,
            cookie_secure=False,
        )
    Settings(
        _env_file=None,
        app_env="production",
        secret_key="s" * 40,
        admin_secret_key="a" * 40,
        cookie_secure=True,
    )


def test_category_keyword_and_recency_scoring_are_explainable():
    now = datetime(2026, 11, 6, 12, tzinfo=timezone.utc)
    fresh = make_article(
        "New language model released",
        "Artificial Intelligence",
        published_at=now - timedelta(hours=2),
        keywords=["machine learning", "language model"],
        summarization={"status": "completed", "short_summary": "A model launch."},
    )
    score = score_article(fresh, ["Artificial Intelligence"], now=now)
    assert score["category_score"] == 1
    assert score["recency_score"] > 0.9
    assert score["content_score"] == 0.75
    assert "Matches your Artificial Intelligence interest" in score["reasons"]
    assert "Recently published" in score["reasons"]

    older = score_article(
        make_article("AI report", "Artificial Intelligence", published_at=now - timedelta(days=20)),
        ["Artificial Intelligence"],
        now=now,
    )
    assert score["relevance_score"] > older["relevance_score"]


def test_keyword_interest_without_category_match_gets_a_reason():
    article = make_article(
        "Machine learning research",
        "Technology",
        keywords=["artificial intelligence", "neural networks"],
    )
    score = score_article(article, ["Artificial Intelligence"])
    assert score["keyword_score"] == 1
    assert "Related to your Artificial Intelligence interest" in score["reasons"]


def test_recommendations_are_user_specific_and_empty_interests_are_safe(monkeypatch):
    now = datetime.now(timezone.utc)
    technology = make_article("A new software platform", "Technology", published_at=now)
    sports = make_article("A football final", "Sports", published_at=now)
    patch_database(monkeypatch, articles=[technology, sports])

    tech_result = recommendations.build_recommendations(make_user(interests=["Technology"]), now=now)
    sports_result = recommendations.build_recommendations(make_user(interests=["Sports"]), now=now)
    empty_result = recommendations.build_recommendations(make_user(interests=[]), now=now)

    assert [item["article"]["title"] for item in tech_result["items"]] == ["A new software platform"]
    assert [item["article"]["title"] for item in sports_result["items"]] == ["A football final"]
    assert empty_result["items"] == []
    assert empty_result["message"]


def test_mocked_account_to_personalized_digest_api_flow(monkeypatch):
    database = patch_database(monkeypatch)
    database["news_articles"].insert_one(make_article(
        "Technology research breakthrough",
        "Technology",
        description="A new technology research breakthrough.",
    ))

    with TestClient(app) as client:
        registered = client.post("/api/v1/auth/register", json={
            "full_name": "Digest Reader",
            "email": "digest.reader@example.com",
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!",
        })
        assert registered.status_code == 201, registered.text

        logged_in = client.post("/api/v1/auth/login", json={
            "email": "digest.reader@example.com",
            "password": "StrongPassword123!",
        })
        assert logged_in.status_code == 200

        interests = client.put(
            "/api/v1/users/interests",
            headers={"Origin": "http://localhost:5173"},
            json={"interests": ["Technology"]},
        )
        assert interests.status_code == 200
        assert interests.json()["interests"] == ["Technology"]

        recommendation_response = client.get("/api/v1/recommendations")
        assert recommendation_response.status_code == 200
        assert [item["article"]["title"] for item in recommendation_response.json()["items"]] == [
            "Technology research breakthrough"
        ]

        digest_response = client.post(
            "/api/v1/digests/generate",
            headers={"Origin": "http://localhost:5173"},
            json={},
        )
        assert digest_response.status_code == 200
        assert digest_response.json()["status"] == "completed"
        digest = digest_response.json()["digest"]
        assert digest["total_articles"] == 1
        assert digest["sections"][0]["articles"][0]["title"] == "Technology research breakthrough"

        history_response = client.get("/api/v1/digests/history")
        assert history_response.status_code == 200
        assert history_response.json()["total"] == 1


def test_recommendation_ranking_deduplicates_event_groups_and_diversifies_categories():
    now = datetime.now(timezone.utc)
    event_id = ObjectId()
    articles = [
        make_article("Technology story A", "Technology", published_at=now, group_id=event_id),
        make_article("Technology story B", "Technology", published_at=now, group_id=event_id),
        make_article("Sports story", "Sports", published_at=now),
    ]
    ranked = rank_articles(articles, ["Technology", "Sports"], now=now, limit=3)
    assert len(ranked) == 2
    assert len({str(item["event_group_id"]) for item in ranked if item["event_group_id"]}) == 1
    assert {item["article"]["category"] for item in ranked} == {"Technology", "Sports"}


def test_category_diversity_prefers_competitive_underrepresented_stories(monkeypatch):
    monkeypatch.setattr(
        diversity_service,
        "get_settings",
        lambda: SimpleNamespace(recommendation_diversity_tolerance=0.12),
    )
    items = [
        {"article": {"_id": "tech-1", "category": "Technology"}, "relevance_score": 0.90},
        {"article": {"_id": "tech-2", "category": "Technology"}, "relevance_score": 0.86},
        {"article": {"_id": "sports-1", "category": "Sports"}, "relevance_score": 0.78},
    ]

    selected = diversity_service.select_diverse_items(items, limit=3)

    assert [item["article"]["category"] for item in selected] == [
        "Technology",
        "Sports",
        "Technology",
    ]


def test_recommendations_fall_back_when_event_representative_is_invalid(monkeypatch):
    now = datetime.now(timezone.utc)
    group_id = ObjectId()
    invalid_representative = make_article(
        "Failed representative",
        "Technology",
        published_at=now,
        group_id=group_id,
        preprocessing_status="failed",
    )
    valid_member = make_article("Valid event coverage", "Technology", published_at=now, group_id=group_id)
    group = {
        "_id": group_id,
        "representative_article_id": invalid_representative["_id"],
        "event_title": "Technology announcement",
        "article_count": 2,
    }
    patch_database(
        monkeypatch,
        articles=[invalid_representative, valid_member],
        groups=[group],
    )

    result = recommendations.build_recommendations(make_user(), now=now)

    assert [item["article"]["title"] for item in result["items"]] == ["Valid event coverage"]


def test_ranker_excludes_invalid_and_failed_articles():
    now = datetime.now(timezone.utc)
    valid = make_article("Valid story", "Technology", published_at=now)
    assert len(rank_articles([
        valid,
        make_article("", "Technology", published_at=now),
        make_article("Failed processing", "Technology", published_at=now, preprocessing_status="failed"),
    ], ["Technology"], now=now)) == 1


def test_timezone_uses_users_local_calendar_date():
    user = make_user(digest_settings={"timezone": "Asia/Kolkata"})
    assert digest.local_digest_date(user, datetime(2026, 11, 6, 19, 0, tzinfo=timezone.utc)) == date(2026, 11, 7)


def test_digest_generation_is_idempotent_and_regeneration_preserves_history(monkeypatch):
    user = make_user()
    article = make_article("Technology report", "Technology", published_at=datetime.now(timezone.utc))
    database = patch_database(monkeypatch, users=[user], articles=[article])
    now = datetime.now(timezone.utc)

    first = asyncio.run(digest.generate_digest_for_user(user, now=now))
    repeated = asyncio.run(digest.generate_digest_for_user(user, now=now))
    regenerated = asyncio.run(digest.generate_digest_for_user(user, regenerate=True, now=now))
    rows = list(database["user_daily_digests"].find({"user_id": user["_id"]}))

    assert first["status"] == "completed"
    assert first["digest"]["total_articles"] == 1
    assert repeated["already_generated"] is True
    assert regenerated["already_generated"] is False
    assert len(rows) == 2
    assert sum(row["is_current"] for row in rows) == 1
    assert all(row["status"] == "completed" for row in rows)


def test_digest_summary_falls_back_to_processed_description(monkeypatch):
    user = make_user()
    article = make_article(
        "Unsummarized report",
        "Technology",
        published_at=datetime.now(timezone.utc),
        summarization={"status": "pending"},
        processed_description="Cleaned description fallback.",
    )
    patch_database(monkeypatch, users=[user], articles=[article])
    result = asyncio.run(digest.generate_digest_for_user(user))
    assert result["digest"]["sections"][0]["articles"][0]["summary"] == "Cleaned description fallback."


def test_digest_repeat_exclusion_applies_across_days_but_regeneration_is_not_excluded(monkeypatch):
    user = make_user()
    article = make_article("Repeated report", "Technology", published_at=datetime.now(timezone.utc))
    database = patch_database(monkeypatch, users=[user], articles=[article])
    first = asyncio.run(digest.generate_digest_for_user(user))
    prior = database["user_daily_digests"].documents[0]
    prior["digest_date"] = (date.fromisoformat(prior["digest_date"]) - timedelta(days=1)).isoformat()
    again = asyncio.run(digest.generate_digest_for_user(user))
    assert first["digest"]["total_articles"] == 1
    assert again["digest"]["total_articles"] == 0


def test_digest_intro_uses_deterministic_fallback_without_ai_key(monkeypatch):
    monkeypatch.setattr(
        digest,
        "get_settings",
        lambda: SimpleNamespace(gemini_api_key="", ai_api_key="", gemini_model="gemini"),
    )
    sections = [{"category": "Technology", "articles": [{"title": "A story", "summary": "Details."}]}]
    result = asyncio.run(digest.generate_digest_introduction(sections))
    assert result == "Here are today's selected stories about Technology."


def test_digest_intro_uses_selected_story_context_and_falls_back_on_provider_error(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "A concise update on the selected technology story."}]}}]}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, *, json, headers):
            assert "A selected story" in json["contents"][0]["parts"][0]["text"]
            return Response()

    monkeypatch.setattr(
        digest,
        "get_settings",
        lambda: SimpleNamespace(gemini_api_key="test-key", ai_api_key="", gemini_model="gemini"),
    )
    monkeypatch.setattr(digest.httpx, "AsyncClient", lambda **kwargs: Client())
    sections = [{"category": "Technology", "articles": [{"title": "A selected story", "summary": "Only selected facts."}]}]
    assert asyncio.run(digest.generate_digest_introduction(sections)).startswith("A concise update")

    class FailingClient(Client):
        async def post(self, *args, **kwargs):
            raise httpx.ConnectError("unavailable")

    monkeypatch.setattr(digest.httpx, "AsyncClient", lambda **kwargs: FailingClient())
    assert asyncio.run(digest.generate_digest_introduction(sections)) == "Here are today's selected stories about Technology."


def test_due_digest_scheduler_respects_user_opt_in_and_local_time(monkeypatch):
    due_user = make_user(digest_settings={
        "digest_enabled": True, "digest_time": "08:00", "timezone": "Asia/Kolkata",
    })
    not_due_user = make_user(digest_settings={
        "digest_enabled": True, "digest_time": "23:00", "timezone": "Asia/Kolkata",
    })
    database = patch_database(monkeypatch, users=[due_user, not_due_user])
    monkeypatch.setattr(
        digest,
        "generate_digest_for_user",
        lambda user, **kwargs: asyncio.sleep(0, result={"status": "completed"}),
    )
    report = asyncio.run(digest.generate_due_digests(now=datetime(2026, 11, 6, 8, 0, tzinfo=timezone.utc)))
    assert report["users_checked"] == 2
    assert report["due"] == 1
    assert report["completed"] == 1


def test_scheduled_user_batches_rotate_fairly(monkeypatch):
    users = [
        make_user(digest_settings={"digest_enabled": True, "digest_time": "00:00"})
        for _ in range(3)
    ]
    database = patch_database(monkeypatch, users=users)
    seen = []

    async def record_user(user, **kwargs):
        seen.append(user["_id"])
        return {"status": "completed"}

    monkeypatch.setattr(digest, "generate_digest_for_user", record_user)
    instant = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)
    for _ in range(3):
        asyncio.run(digest.generate_due_digests(batch_size=1, now=instant))

    assert len(set(seen)) == 3
    assert database["digest_scheduler_state"].find_one({"_id": "daily_digest_user_cursor"})["last_user_id"] in {
        user["_id"] for user in users
    }


def test_concurrent_digest_claim_returns_in_progress(monkeypatch):
    user = make_user()
    database = patch_database(monkeypatch, users=[user])
    digest_date = digest.local_digest_date(user).isoformat()
    database["user_digest_generation_claims"].insert_one({
        "_id": f"{user['_id']}:{digest_date}",
        "user_id": user["_id"],
        "digest_date": digest_date,
        "token": ObjectId(),
        "lease_until": datetime.now(timezone.utc) + timedelta(minutes=5),
    })
    result = asyncio.run(digest.generate_digest_for_user(user))
    assert result["status"] == "in_progress"
    assert database["user_daily_digests"].documents == []


def test_digest_apis_scope_data_to_authenticated_user(monkeypatch):
    user = make_user()
    other_user = make_user()
    article = make_article("Technology report", "Technology", published_at=datetime.now(timezone.utc))
    patch_database(monkeypatch, users=[user, other_user], articles=[article])
    with TestClient(app) as auth_client:
        unauthorized = auth_client.get("/api/v1/recommendations")
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        with TestClient(app) as client:
            generated = client.post("/api/v1/digests/generate", json={})
            today = client.get("/api/v1/digests/today")
            history = client.get("/api/v1/digests/history")
            settings_response = client.get("/api/v1/digests/settings")
            stats = client.get(
                "/api/v1/admin/digests/stats",
                headers={"X-Admin-Key": "development-admin-key"},
            )
            digest_id = generated.json()["digest"]["id"]
            app.dependency_overrides[get_current_user] = lambda: other_user
            denied = client.get(f"/api/v1/digests/{digest_id}")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert unauthorized.status_code == 401
    assert generated.status_code == 200
    assert today.json()["status"] == "completed"
    assert history.json()["total"] == 1
    assert settings_response.json()["interests"] == ["Technology"]
    assert stats.json()["successful_digests"] == 1
    assert denied.status_code == 404


def test_digest_settings_api_updates_settings_without_overwriting_interests(monkeypatch):
    user = make_user(interests=["Technology", "Science"])
    database = patch_database(monkeypatch, users=[user])
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        with TestClient(app) as client:
            response = client.put("/api/v1/digests/settings", json={
                "digest_enabled": True,
                "digest_frequency": "daily",
                "digest_time": "07:15",
                "timezone": "Europe/London",
                "articles_per_digest": 8,
            })
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    stored = database["users"].find_one({"_id": user["_id"]})
    assert response.status_code == 200
    assert stored["interests"] == ["Technology", "Science"]
    assert stored["digest_settings"]["timezone"] == "Europe/London"


def test_admin_digest_statistics_requires_admin(monkeypatch):
    patch_database(monkeypatch)
    with TestClient(app) as client:
        denied = client.get("/api/v1/admin/digests/stats")
        allowed = client.get(
            "/api/v1/admin/digests/stats",
            headers={"X-Admin-Key": "development-admin-key"},
        )
    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json()["successful_digests"] == 0


def test_user_cannot_generate_or_retrieve_another_users_digest(monkeypatch):
    user = make_user()
    other = make_user()
    article = make_article("Technology report", "Technology", published_at=datetime.now(timezone.utc))
    patch_database(monkeypatch, users=[user, other], articles=[article])
    generated = asyncio.run(digest.generate_digest_for_user(user))
    app.dependency_overrides[get_current_user] = lambda: other
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/digests/{generated['digest']['id']}")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 404
