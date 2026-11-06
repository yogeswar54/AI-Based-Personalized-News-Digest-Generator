# AI-Based Personalized News Digest Generator

A modular full-stack application for collecting, processing, summarizing, and organizing news content for personalized delivery. Stages 1–8 provide a responsive React frontend, FastAPI backend, MongoDB-backed user and article storage, registration and profile/interest management, NewsAPI and RSS collection, AI-assisted preprocessing and categorization, AI-generated summaries, semantic event grouping, personalized recommendations, in-app daily digests, and test/deployment preparation.

## Problem and proposed solution

News stories are spread across publishers and can be repetitive or difficult to scan. This application collects articles from configured news sources, processes and groups related coverage, then ranks stories against each authenticated user's saved interests and generates a locally scheduled digest. When optional AI services are not configured or available, supported processing paths use deterministic/provider fallbacks.

## Objectives

- Establish independent frontend and backend applications that are easy to extend.
- Keep configuration and credentials outside source code.
- Support registration, login, profile updates, and interest management.
- Collect news through provider adapters and store normalized articles in MongoDB.
- Process collected articles with text cleaning, normalization, keyword extraction, and AI-based categorization.
- Generate short, medium, and detailed summaries with supporting key points and extracted facts.
- Identify exact duplicate records separately from semantically related coverage and group stories about the same event.
- Rank shared news separately for each user using saved interests, recency, keywords, and content completeness.
- Generate and store personalized daily digests with local-time and timezone preferences.
- Keep the system resilient when AI services are unavailable by using provider and rule-based fallbacks.

## Implemented and future scope

Stages 1–8 are implemented in this repository. Email/push delivery, production-grade distributed scheduling, and broader dashboard analytics are future enhancements, not current features.

## Technology

- Frontend: React, Vite, JavaScript, Tailwind CSS, React Router DOM, Axios.
- Backend: Python, FastAPI, Uvicorn, Pydantic Settings, PyMongo.
- Database: MongoDB, including MongoDB Atlas-compatible connection URIs.

## Project structure

```text
.
├── backend/
│   ├── app/
│   │   ├── api/v1/           # Versioned auth, user, news, and admin routes
│   │   ├── core/             # Security, dependencies, and error handlers
│   │   ├── database/         # MongoDB lifecycle and access
│   │   ├── models/           # User and article document models
│   │   ├── schemas/          # Request and response validation
│   │   ├── services/         # Auth, users, providers, and processing
│   │   ├── config.py         # Environment-backed settings
│   │   └── main.py           # FastAPI app, routes, and lifespan
│   ├── tests/
│   ├── .env.example
│   └── requirements.txt
├── docs/architecture.md
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── layouts/
│   │   ├── pages/
│   │   ├── services/
│   │   ├── App.jsx
│   │   ├── index.css
│   │   └── main.jsx
│   ├── .env.example
│   ├── package.json
│   └── vite.config.js
├── .env.example
└── .gitignore
```

## Prerequisites

- Python 3.10 or later (developed with Python 3.12).
- Node.js 20.19+ or 22.12+ and npm (Vite requirement).
- A MongoDB instance for database-backed development: local MongoDB or a MongoDB Atlas URI. The API can also start without a reachable MongoDB instance.

## Configure environment

From the repository root, copy the backend example file:

```powershell
Copy-Item backend\.env.example backend\.env
```

Or, if you prefer the root template:

```powershell
Copy-Item .env.example backend\.env
```

Edit `backend/.env` and set `MONGODB_URI` and `DATABASE_NAME`. For Atlas, use the connection URI from your Atlas cluster and keep its credentials in this ignored file. Set `FRONTEND_URL` to the frontend origin if it differs from `http://localhost:5173`. Set `GEMINI_API_KEY` to enable AI categorization and summaries; the legacy `AI_API_KEY` is also accepted as a fallback. Model and scheduling settings are backend-only. Never put real keys in frontend environment files or commit `.env` files. For staging/production set `APP_ENV` accordingly, provide unique `SECRET_KEY` and `ADMIN_SECRET_KEY` values of at least 32 characters, and set `COOKIE_SECURE=true`; the application rejects the development defaults in those environments.

Automatic summarization is disabled by default. To enable it in `backend/.env`, set `NEWS_SUMMARIZATION_ENABLED=true` and tune `NEWS_SUMMARIZATION_INTERVAL_MINUTES`, `NEWS_SUMMARIZATION_BATCH_SIZE`, and `NEWS_SUMMARIZATION_MAX_INPUT_CHARS`. The scheduled job summarizes only articles whose Stage 4 preprocessing has completed. In a multi-worker deployment, run the scheduler in only one process to prevent duplicate scheduled work.

Set up the frontend environment (optional; the default points to the local API):

```powershell
Copy-Item frontend\.env.example frontend\.env
```

## Install and run the backend

From the repository root, in PowerShell:

```powershell
cd backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m app.main
```

The backend reads `backend/.env`. If PowerShell blocks activation, allow scripts for the current process with `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then activate again. Alternatively, invoke `.venv\Scripts\python.exe` and `.venv\Scripts\uvicorn.exe` directly.

The development server uses `API_HOST` and `API_PORT` from that file (defaults: `127.0.0.1` and `8000`). `PORT` is also accepted for hosting platforms that inject it. For production, bind to `0.0.0.0` and use the platform's port; see [docs/deployment.md](docs/deployment.md).

The app attempts a MongoDB ping on startup. If MongoDB is unavailable, it logs the connection failure and continues running so non-database routes remain usable. Feature services create their indexes when they first access their collections. `GET /api/v1/health` is a liveness/status endpoint; `GET /api/v1/health/ready` returns HTTP 503 until MongoDB is reachable.

## Install and run the frontend

In another terminal, from the repository root:

```powershell
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (normally `http://localhost:5173`). The frontend API client uses `VITE_API_BASE_URL`, defaulting to `http://localhost:8000/api/v1`.

## Tests and API checks

Run the backend tests with mocked external services from `backend/`:

```powershell
python -m pytest -q
```

Run frontend component/interaction tests and create a production build from `frontend/`:

```powershell
npm test
npm run build
```

No live NewsAPI, Gemini, Atlas, or sentence-transformer download is required for these tests. The browser test suite uses jsdom and mocked service calls; it does not replace full browser/mobile E2E testing.

With the backend running, verify liveness and readiness:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ready
```

The liveness response reports whether MongoDB is connected. Readiness returns HTTP 503 when it is unavailable. Interactive API documentation is available at `http://127.0.0.1:8000/docs` in the current configuration.

The root endpoint is `GET /`. See [docs/architecture.md](docs/architecture.md) and [docs/deployment.md](docs/deployment.md) for system and manual deployment details.

## Stage 5: AI summarization

The backend sends cleaned article content (up to `NEWS_SUMMARIZATION_MAX_INPUT_CHARS`) to the configured Gemini model. When full content is unavailable, the service uses the Stage 4 cleaned description, then the original description. It does not scrape publisher sites. The model returns short (about 30–50 words), medium (80–120 words), and detailed (150–200 words) summaries when the source supports those lengths, along with up to five key points and explicit article facts. Outputs are validated before being saved under the article's `summarization` field. The UI labels summaries as AI-generated and provides a length selector on each article details page.

Automatic summarization remains opt-in to control API usage. Articles are claimed atomically before an AI request, so overlapping manual and scheduled runs do not generate duplicate summaries for the same article. Failed articles can be retried using the batch endpoint. Existing article fields and Stage 4 metadata remain intact; when a provider refresh changes article text, previous processing and summary results are invalidated.

### Summary API

Admin endpoints require the configured `ADMIN_SECRET_KEY` in the `X-Admin-Key` header:

```powershell
$adminHeaders = @{ "X-Admin-Key" = "your-admin-secret" }
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/admin/news/ARTICLE_ID/summarize" `
  -Headers $adminHeaders

Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/admin/news/summarize?batch_size=10&retry_failed=true" `
  -Headers $adminHeaders

Invoke-RestMethod -Method Get `
  -Uri "http://127.0.0.1:8000/api/v1/news/ARTICLE_ID/summary"

Invoke-RestMethod -Method Get `
  -Uri "http://127.0.0.1:8000/api/v1/admin/news/summarization/stats" `
  -Headers $adminHeaders
```

Add `?regenerate=true` to the single-article or batch POST URL to regenerate completed or skipped summaries. The batch response includes `total_candidates`, `processed`, `failed`, and `skipped`. Summary retrieval returns a status (`missing`, `pending`, `processing`, `completed`, `failed`, or `skipped`) and a summary object when available. Run all backend tests, including mocked Stage 5 AI tests, with `python -m pytest` from `backend/`; no live Gemini key is needed for tests.

Example completed-summary response:

```json
{
  "article_id": "665f1a2b3c4d5e6f7890abcd",
  "status": "completed",
  "summary": {
    "short_summary": "Example Labs announced a product update.",
    "medium_summary": "Example Labs announced a product update in London...",
    "detailed_summary": "Example Labs announced a product update...",
    "key_points": ["The company announced an update."],
    "important_facts": {
      "people": [],
      "organizations": ["Example Labs"],
      "locations": ["London"],
      "dates": [],
      "numbers": []
    },
    "model": "gemini-2.5-flash",
    "source_used": "full_content",
    "generated_at": "2026-11-06T12:00:00+00:00",
    "error": null
  }
}
```

## Stage 6: semantic duplicate detection and news groups

Exact duplicates are checked using normalized article URLs and provider/external IDs. Semantic grouping is a separate step: the backend prepares cleaned article text, creates CPU sentence-transformer embeddings, retrieves a bounded set of recent candidates in the same category, and compares cosine similarity. Articles are grouped only when similarity and event-context evidence pass configured thresholds; each publisher article remains a separate record. The system stores embeddings and processing metadata on `news_articles`, and creates `news_event_groups` documents containing group membership and a representative article. Vectors are omitted from API responses.

The default model is `sentence-transformers/all-MiniLM-L6-v2`. Install backend requirements to enable the service; the model is loaded lazily and may be downloaded the first time deduplication runs. Tests mock model output and do not download it. Automatic scheduled deduplication is disabled by default; enable it with `NEWS_DEDUPLICATION_ENABLED=true`. As with the existing scheduler, run only one scheduler process in a multi-worker deployment. The implementation uses bounded category/date candidate queries rather than a MongoDB vector index, so revisit retrieval strategy as the article collection grows.

Thresholds and bounds can be tuned in `backend/.env`: `NEWS_DUPLICATE_THRESHOLD` (0.85), `NEWS_SIMILARITY_THRESHOLD` (0.75), `NEWS_SIMILARITY_LOOKBACK_DAYS` (7), `NEWS_SIMILARITY_CANDIDATE_LIMIT` (100), `NEWS_EMBEDDING_BATCH_SIZE` (16), and `NEWS_DEDUPLICATION_BATCH_SIZE` (25). Failed items are retried by setting `retry_failed=true` on the batch endpoint.

The admin API requires `X-Admin-Key`:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/admin/news/deduplicate?batch_size=25" `
  -Headers $adminHeaders

Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/admin/news/deduplicate?batch_size=25&retry_failed=true" `
  -Headers $adminHeaders

Invoke-RestMethod -Method Get `
  -Uri "http://127.0.0.1:8000/api/v1/admin/news/deduplication/stats" `
  -Headers $adminHeaders
```

Public endpoints list groups (`GET /api/v1/news/groups`), fetch group details (`GET /api/v1/news/groups/{group_id}`), and retrieve related coverage (`GET /api/v1/news/{article_id}/related`). The authenticated news feed displays multi-source groups and preserves single-source articles in the regular feed.

## Stage 7: recommendations and daily digests

Recommendations are calculated per authenticated user from the interests already stored on that user's Stage 2 profile. The default explainable score is a weighted combination of category match (60%), keyword match (15%), recency (15%, with a 72-hour decay), and content completeness (10%). Weights, the article lookback, the bounded candidate limit, and the category diversity tolerance are configurable with `RECOMMENDATION_*` settings. Recommendations require an interest match, prefer processed and summarized articles, skip failed preprocessing and exact duplicates, and return a score plus evidence-based reason strings. The selection step uses Stage 6 event groups to show one eligible representative per event and prefers underrepresented categories only when their stories score within the configured tolerance, rather than forcing a rigid quota.

Digest preferences are saved under each existing user document's `digest_settings` object and never replace the user's interests. Defaults are disabled, daily at 08:00 UTC, with 10 stories. Each user can set an IANA timezone, time, and count from **Digest settings**. Generation computes the date in that timezone, reuses available Stage 5 summaries with a cleaned description fallback, groups selected stories by category, and stores only story references/display fields in `user_daily_digests`. A deterministic introduction is used when Gemini is not configured or unavailable; when configured, one concise introduction call uses only the chosen stories. Article summaries are never regenerated.

Completed digests are idempotent for a user and local calendar date. Explicit regeneration adds a history version and makes it current. A MongoDB unique current-digest index and a per-user/date lease prevent duplicate generation requests. Recently used article and event references are excluded for `DIGEST_REPEAT_EXCLUSION_DAYS` (default 2); newer publication or event-group updates may still appear. Normal news browsing is unaffected.

### Stage 7 APIs

User routes require the existing cookie or bearer authentication. User IDs are always derived from the authenticated account:

```powershell
# Personalized recommendations
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/recommendations?page=1&limit=20"

# View, update, and manually generate your digest
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/digests/settings"
Invoke-RestMethod -Method Put `
  -Uri "http://127.0.0.1:8000/api/v1/digests/settings" `
  -ContentType "application/json" `
  -Body '{"digest_enabled":true,"digest_frequency":"daily","digest_time":"08:00","timezone":"Asia/Kolkata","articles_per_digest":10}'
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/digests/generate" `
  -ContentType "application/json" `
  -Body '{"regenerate":false}'

Invoke-RestMethod "http://127.0.0.1:8000/api/v1/digests/today"
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/digests/history?page=1&limit=10"
```

`POST /api/v1/digests/generate` accepts `{"regenerate":true}` only for an intentional new version. `GET /api/v1/digests/{digest_id}` verifies ownership and returns 404 for another user's digest. `GET /api/v1/admin/digests/stats` is protected by `X-Admin-Key`.

Example `GET /api/v1/digests/today` response:

```json
{
  "status": "completed",
  "digest": {
    "digest_date": "2026-11-07",
    "timezone": "Asia/Kolkata",
    "title": "Your Daily News Digest",
    "introduction": "Here are today's selected stories about Technology.",
    "sections": [
      {
        "category": "Technology",
        "articles": [
          {
            "article_id": "665f1a2b3c4d5e6f7890abcd",
            "event_group_id": "665f1a2b3c4d5e6f7890abce",
            "title": "Example product update",
            "summary": "The company announced a product update.",
            "source": "Example News",
            "published_at": "2026-11-07T06:30:00+00:00"
          }
        ]
      }
    ],
    "total_articles": 1,
    "status": "completed"
  }
}
```

The shared APScheduler checks opted-in users in configured batches when `DIGEST_SCHEDULER_ENABLED=true`; user preferences determine each user's due local time. It uses IANA `zoneinfo` rules, including daylight-saving changes, and a per-user/date Mongo claim to avoid duplicate work. Like the other existing in-process scheduler jobs, it must run in exactly one API process in a multi-worker deployment; set this option only on the designated scheduler instance. Manual generation remains available when the scheduler is disabled.

MongoDB adds `user_daily_digests` (unique user/date/generation and one-current-digest indexes) and `user_digest_generation_claims` (unique user/date lease index). Digest settings are nested in `users.digest_settings`; recommendations do not create per-user article copies. Run all backend tests, including the mocked Stage 7 tests, with `python -m pytest` from `backend/`.

## Stage 8: testing and deployment preparation

The backend tests use isolated fake Mongo collections and mocked HTTP/AI/model boundaries; the frontend Vitest suite covers representative forms, route guards, news filters, article summary selection, related coverage, recommendations, digest history/settings, and loading/error/empty states. Page-level route splitting and lazy-loaded news images reduce initial frontend work. Backend requests apply exact-origin CORS, cookie-origin checks for state-changing requests, bounded provider retries, non-secret health/readiness reporting, and common security headers.

See [docs/deployment.md](docs/deployment.md) for the Render, Vercel, and MongoDB Atlas manual deployment checklist. These files are templates, not a deployment. External services, real Atlas index behavior, production browser cookie behavior, and mobile layouts must still be verified in the target environment. Email/push delivery remains out of scope.
