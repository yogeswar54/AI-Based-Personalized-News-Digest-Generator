# Manual deployment guide

The repository includes a Render Blueprint in `backend/render.yaml` and a Vercel SPA rewrite in `frontend/vercel.json`. They are configuration templates only; no resources are created or deployed by this project.

## 1. Prepare MongoDB Atlas

1. Create an Atlas project and cluster, then create a database user with a strong unique password.
2. Grant that user only the database permissions required by this application; do not use an Atlas project-owner credential.
3. Configure Atlas Network Access to allow traffic from the backend. Prefer a fixed egress IP and a narrow allowlist. If the selected Render plan does not provide fixed outbound addresses, choose a hosting/network option that supports restricted access instead of permanently allowing all IPs.
4. Copy the TLS-enabled connection URI and set the database name. Add the URI only as a Render secret; never commit it or put it in a `VITE_*` setting.
5. Before production index changes or upgrades, take and verify an Atlas backup. The app creates indexes on existing collections and does not drop collections or migrate/delete documents.

The application currently provisions indexes lazily when its services first access a collection. It creates a unique user email index, article canonical URL index, operational query indexes, and unique digest generation/current-digest indexes. Existing duplicate data can prevent a new unique index from being created; resolve such conflicts with a reviewed, backed-up manual data repair. No automatic cleanup is performed.

## 2. Deploy the backend to Render

1. Connect the repository in Render and use the Blueprint file `backend/render.yaml` (or create a Web Service manually with **Root Directory** `backend`).
2. Use build command `pip install -r requirements.txt` and start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
3. Configure `MONGODB_URI` and `FRONTEND_URL` in the Render dashboard. The Blueprint generates `SECRET_KEY` and `ADMIN_SECRET_KEY`; keep those generated values private.
4. Keep `APP_ENV=production`, `COOKIE_SECURE=true`, and configure `COOKIE_SAMESITE` to the actual site topology. If the frontend and API are on different registrable domains, browser cookie auth needs `SameSite=None; Secure`; some browsers block third-party cookies even then. Prefer custom frontend and API subdomains under the same registrable domain (for example `app.example.com` and `api.example.com`) to avoid third-party-cookie restrictions.
5. Set `NEWS_API_KEY` and `GEMINI_API_KEY` only when those integrations are required. The sample config leaves automatic summarization, deduplication, and digest scheduling disabled; enable only the jobs you intend to run.
6. Deploy one backend instance initially and verify the Render health check `GET /api/v1/health/ready`. It returns 503 when MongoDB cannot be reached. The liveness route `GET /api/v1/health` remains available to report API status and MongoDB dependency state.

The app's APScheduler runs news collection and preprocessing whenever the API process starts. Summarization, semantic deduplication, and digest generation are opt-in. Because APScheduler is process-local, do not scale the web service to multiple instances/workers while jobs are enabled unless you run scheduler jobs in exactly one designated process. Duplicate scheduler execution is not coordinated across hosts.

The sentence-transformers/CPU inference dependency is large and model download happens on first semantic deduplication. Check the target plan's build time, memory, and disk limits before enabling deduplication; its behavior has not been validated on Render.

## 3. Deploy the frontend to Vercel

1. Import the same repository into Vercel and set **Root Directory** to `frontend`.
2. Use the Vite framework preset and default `npm install` / `npm run build` commands.
3. Configure `VITE_API_BASE_URL` as `https://<your-api-host>/api/v1`. It is a public API URL, not a secret.
4. Keep `frontend/vercel.json` so direct navigation to React Router paths serves the SPA entry point.
5. Set the exact production frontend origin as the backend `FRONTEND_URL`, then redeploy the backend so CORS and cookie-origin checks allow that origin.
6. Open the frontend and verify registration/login, news API calls, recommendations, and digest routes. Check the browser network console for CORS or cookie restrictions.

## 4. Production checklist

- Replace all example credentials; use unique random secrets of at least 32 characters. Production configuration rejects the built-in development secret defaults.
- Keep Atlas, NewsAPI, and Gemini credentials exclusively in Render's backend environment.
- Restrict Atlas network access and apply least privilege to its database user.
- Use HTTPS for both sites. Cookie auth requires `COOKIE_SECURE=true`; use `COOKIE_SAMESITE=none` only when cross-site requests require it.
- The backend checks the `Origin` header on cookie-authenticated state-changing requests. Configure `FRONTEND_URL` to one trusted origin; do not use a wildcard.
- Apply authentication rate limits at the hosting edge/reverse proxy. The application does not implement a distributed rate limiter.
- Review logs for application errors without adding credentials, bearer tokens, or article/provider URLs containing secret query parameters.
- Configure backups, alerting, and a single scheduler owner before accepting production traffic.
- Review the provider API terms, quotas, and costs. No paid resources are provisioned by this repository.

Deployment, external API connectivity, Atlas connectivity, and browser behavior under third-party cookie restrictions must be verified in the target accounts; they are not covered by local automated tests.
