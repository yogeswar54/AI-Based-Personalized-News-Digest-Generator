# Architecture

## Frontend

The Vite application mounts React from `src/main.jsx`. `App.jsx` owns client-side routing, `layouts/AppLayout.jsx` provides the shared page frame, and the navigation and landing page are kept in separate components. `services/api.js` is the shared Axios client; its base URL comes from `VITE_API_BASE_URL` and defaults to the versioned local API. Feature-specific pages, hooks, and state can be added as product requirements are implemented.

Tailwind CSS is integrated through the Vite plugin and imported once in `src/index.css`. This follows the current Tailwind v4 Vite setup rather than the older PostCSS/Tailwind v3 directives.

Authentication state is managed by `context/AuthContext.jsx`; guest and protected routes are declared in `routes/AppRoutes.jsx`. Feature-specific API calls live in `services/`, keeping page components separate from request configuration.

## Backend

`app/main.py` creates the FastAPI application, configures CORS and lifespan handling, and registers the versioned API router and centralized exception handlers. HTTP endpoints live in `app/api/v1/`; future route modules can delegate to services rather than embedding business logic in route handlers. `app/config.py` validates environment-backed settings through Pydantic Settings. `app/core/` contains cross-cutting application behavior, and `app/database/` owns database lifecycle and access.

## Database connection flow

At startup, FastAPI's lifespan handler asks the database module to create a PyMongo client using `MONGODB_URI` and select `DATABASE_NAME`. The module pings MongoDB before exposing the database handle. A connection error is logged and leaves the handle unavailable, but does not stop the API from serving non-database routes. On shutdown, the client is closed. Feature services use the database handle and create only the indexes they need when accessed.

Use a local URI such as `mongodb://localhost:27017` or an Atlas-provided URI. Credentials belong only in the backend environment file, never in the browser bundle.

## Frontend-to-backend communication

The browser calls the FastAPI v1 endpoints through the shared Axios instance. In production the backend permits only the configured `FRONTEND_URL`; local development/test origins are added only in those environments. Cookie-authenticated state-changing requests must include an allowed `Origin`, providing CSRF mitigation without changing the existing HTTP-only cookie and bearer-token support. Production cross-site cookies require HTTPS, `COOKIE_SECURE=true`, and `COOKIE_SAMESITE=none`; custom frontend/API subdomains on the same registrable domain are preferable because browser third-party-cookie restrictions may block cross-site cookies regardless. Keep HTTP contract validation and status codes at the API boundary, with business rules implemented in services. Avoid importing backend-only configuration or credentials into the Vite application.

The API adds `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and `Permissions-Policy` headers. The liveness route reports MongoDB status, while `/api/v1/health/ready` returns 503 when MongoDB is unavailable. Authentication rate limiting is not implemented in-process; production deployments should apply it at the hosting edge or reverse proxy.

## Stage 2: authentication and interests

The `/api/v1/auth` routes delegate registration and login to `auth_service.py`. Password hashes are stored in MongoDB, and successful login sets an HTTP-only cookie containing a signed access token. `get_current_user` validates the cookie or bearer token before protected user routes expose or update profile and interest data. The supported interest list is centralized in `user_service.py` and is shared by the interest API and categorization logic.

## Stage 3: news collection

The admin collection endpoint and scheduler invoke `news_collector.py`, which asks the NewsAPI and RSS provider adapters for items. RSS requests are asynchronous and bounded by an HTTP timeout so a slow feed does not block the FastAPI event loop. Provider requests retry transient transport errors, HTTP 429s, and 5xx responses once with a short backoff; NewsAPI and Gemini credentials are sent in headers rather than URLs. `news_normalizer.py` maps provider-specific fields into the shared article shape, accepts only absolute HTTP(S) article URLs, and derives canonical URLs; the collector checks duplicates before inserting or refreshing a MongoDB article and distinguishes duplicate-key races from other write failures. Public news endpoints provide filtering, pagination, categories, sources, and individual article retrieval.

## Stage 4: preprocessing and AI categorization

The project now includes a preprocessing layer that cleans article titles and descriptions, normalizes text, extracts keywords, and classifies articles into the existing supported interest categories. `app/services/preprocessing/` owns the cleaning and normalization tasks, while `app/services/ai/gemini_classifier.py` handles the Gemini JSON-based classification call when an API key is configured. The fallback order is AI -> provider category -> rule-based classification -> default category, and each article stores its `classification_method`, `category_confidence`, `preprocessing_status`, and `preprocessing_error` in MongoDB.

The scheduler in `app/services/news/news_scheduler.py` runs both collection and preprocessing jobs without overlapping. Admin-only endpoints in `app/api/v1/admin.py` trigger batch preprocessing, retry failed items, and return preprocessing statistics. This keeps Stage 4 isolated from the collection pipeline while preserving compatibility with the existing article schema and API contracts.

## Stage 5: AI summarization

`app/services/summarization/` owns prompt construction, strict JSON output validation, content selection, and Mongo persistence. The service reuses the backend-only Gemini key/model settings and bounds the article text sent to the provider. It selects full content first, then the cleaned Stage 4 description, then the original description; it never scrapes the publisher website. Summaries, key points, facts, source type, model, status, error, and generation timestamp live in the existing `news_articles.summarization` document field, preserving older article records and preprocessing metadata.

Before calling Gemini, a conditional Mongo update claims the article and marks it processing. Completed summaries are skipped unless regeneration is requested, and failed summaries are selected for batch retry only when requested. A stale processing claim can be recovered after 30 minutes. Batch jobs are limited in size and run only for Stage 4-completed articles. The existing APScheduler instance is extended; automatic summarization is disabled by default and is safest to run in a single API worker or a dedicated scheduler process.

The admin API provides single and batch triggers plus statistics. `GET /api/v1/news/{article_id}/summary` returns one of `missing`, `pending`, `processing`, `completed`, `failed`, or `skipped`; summary text is clearly labeled as AI-generated in the React news feed and article details page. API credentials are never sent to or included in frontend bundles.

## Stage 6: semantic duplicate detection and event grouping

`app/services/deduplication/` separates text preparation, lazy CPU embedding generation, vector similarity, and event-group membership. Exact duplicates are checked using normalized canonical URLs and provider/external IDs before embeddings are generated; sharing a publisher domain alone never makes articles duplicates. Semantic candidate retrieval is constrained by category, publication date, model version, and a configurable result cap. Cosine similarity is only one signal: matching articles must also share event wording or extracted entities, with stronger context required for lower-confidence similarity matches.

The `news_articles` documents hold embedding status/model/vector, duplicate-processing state, and an optional `event_group_id`. Vectors are internal and are removed by article serialization. `news_event_groups` documents hold member article IDs, a representative article, event title/category/keywords, and timestamps. Membership updates are idempotent, and representative choice favors complete content and completed summaries. When a provider refresh changes article text, Stage 4/5/6 results and group membership are invalidated so stale analysis is not reused.

Admin-only endpoints trigger single-batch processing and expose counts. Public endpoints return group lists/details and related articles, while the React news feed presents multi-source groups without merging or losing each publisher's original article. Scheduled deduplication is opt-in. The embedding model is loaded lazily and may be downloaded on first use; tests mock inference. Candidate search currently uses indexed category/date filters with a bounded recent candidate set, not a database vector index. This is intentionally simple for the current scale and should be reevaluated as article volume grows. As with other APScheduler jobs, run a single scheduler process in multi-worker deployments.

## Stage 7: personalized recommendations and daily digests

The `recommendation` services rank records from the shared `news_articles` collection for the authenticated user, using the existing `users.interests` list. Category match, article keyword overlap, publication recency, and content completeness form a normalized weighted score; explanations include only signals actually present. Recommendations ignore articles with failed preprocessing or exact-duplicate references, prefer an eligible Stage 6 group representative (and fall back to other valid group coverage if it is unavailable), and prefer underrepresented categories only when their stories score within the configured diversity tolerance. User IDs are never accepted as recommendation selectors from clients.

`GET /api/v1/recommendations` is protected by the existing `get_current_user` dependency. `app/services/digest/digest_service.py` applies recommendation ranking to a user's configured article count, groups non-empty results into category sections, reuses Stage 5 short summaries, and falls back to processed/original descriptions. It sends only those selected story titles and summaries to Gemini for one concise introduction; missing credentials, malformed responses, and provider failures use a deterministic introduction instead.

Digest preferences are stored at `users.digest_settings`, independently of the existing interests field. `DigestSettings` validates the local `HH:MM` time, IANA timezone via Python `zoneinfo`, and story count. Local digest dates and due checks are computed in each user's timezone, so daylight-saving transitions use the installed timezone database. `user_daily_digests` stores references and presentation data rather than full article copies. A unique per-user/date/generation index preserves regenerated versions; a partial unique current index permits one current digest per local date. `user_digest_generation_claims` adds a lease per user/date to prevent concurrent generation. Recent article/group references are excluded for a configurable short window, but updated group coverage can surface again.

User endpoints under `/api/v1/digests` provide settings, manual generation, today's digest, history, and ownership-checked retrieval. `/api/v1/admin/digests/stats` uses the existing admin key. The frontend adds authenticated recommendation, daily digest/history, and settings screens and links them from the dashboard/navigation.

The existing APScheduler instance can run `generate_due_digests` at a configured interval. Scheduled work is globally opt-in with `DIGEST_SCHEDULER_ENABLED` and individually opt-in with `users.digest_settings.digest_enabled`; users are evaluated in bounded batches and the generation claim makes repeated checks safe. APScheduler is in-process, not a distributed scheduler: in a multi-worker deployment designate one scheduler process (disable the job in all other workers). Generation and history remain available through authenticated APIs regardless of scheduler state.

## Future modules

External email, push, and messaging delivery remain later-stage work. They should consume stored digests without coupling delivery to shared collection, preprocessing, summarization, or event-grouping pipelines.

## Stage 8: verification and operations

Backend tests exercise service and API behavior using fake collections and mocked AI/provider/model calls; frontend tests use Vitest, React Testing Library, and jsdom. They do not prove live MongoDB index contention, provider connectivity, real model inference, browser-specific cookie behavior, or physical-device responsive rendering. Render and Vercel configuration templates and the manual Atlas checklist are in `docs/deployment.md`; no service is deployed by the repository.

All scheduled jobs use a process-local APScheduler. Collection and preprocessing start with the application; summarization, deduplication, and digest jobs are configurable. Run a single application/scheduler process until scheduler ownership is separated. The semantic embedding stack can require substantial memory, disk, model download time, and cold-start time, so validate the selected host before enabling it.
