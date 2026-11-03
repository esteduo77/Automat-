# Automation Hub

Automation Hub is a visual workflow automation application built with React, TypeScript, FastAPI, SQLAlchemy and OpenAI.

## Features in this branch

- Visual workflow canvas with configurable blocks and graph validation.
- Manual, interval-schedule and signed generic-webhook triggers.
- IF/ELSE branches, data transformation, result blocks and OpenAI Responses API actions.
- User accounts, Argon2 password hashing, JWT sessions and per-user workflow isolation.
- Google Gmail/Drive and Microsoft Graph OAuth connections with encrypted tokens.
- Read operations plus approved email-send and cloud text-file create/update actions.
- Mandatory server-side human approval before external write actions.
- Separate database-backed worker for queued runs and interval schedules.
- Execution history and approval decisions.

Native Gmail Watch/Pub/Sub, Google Drive change channels and Microsoft Graph subscriptions are supported through the provider-events API. The worker renews subscriptions before expiry. The generic signed webhook remains available separately.

## Run locally

Requirements: Python 3.12+, Node.js 20+, npm.

1. Copy `.env.example` to `.env`.
2. Generate secrets and put them in `.env`:
   - `JWT_SECRET`: a unique random value of at least 32 characters.
   - `OAUTH_ENCRYPTION_KEY`: output of `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
3. Install and start the backend from the repository root:

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

4. In another terminal, start the worker from the repository root:

```bash
python -m backend.app.worker
```

5. In a third terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. API documentation: http://localhost:8000/docs. Register an account before creating workflows.

OpenAI blocks require `OPENAI_API_KEY`. Google/Microsoft integrations additionally require their OAuth client ID/secret and the callback URLs configured in each provider console:
- Google: `http://localhost:8000/api/integrations/google/callback`
- Microsoft: `http://localhost:8000/api/integrations/microsoft/callback`

The frontend uses relative `/api` URLs, proxied by Vite during local development.

## Run with Docker Compose

Install Docker Desktop or Docker Engine with the Compose plugin. Copy `.env.example` to `.env`, set real values for `JWT_SECRET` and `OAUTH_ENCRYPTION_KEY`, then run:

```bash
docker compose up --build
```

Open http://localhost:8080. The API is also exposed at http://localhost:8000 and docs at http://localhost:8000/docs. Compose runs the API, a separate worker and the built frontend; SQLite data is persisted in the `automation_hub_data` volume. To stop: `docker compose down`. To also erase the local database: `docker compose down -v`.

For Google/Microsoft OAuth with Compose, use the callback URLs above and set `FRONTEND_BASE_URL=http://localhost:8080`.

## Native provider event subscriptions

Set `PUBLIC_BASE_URL` to the externally reachable HTTPS origin. For Gmail, configure a Google Cloud Pub/Sub topic, grant Gmail permission to publish to it, and configure a push subscription targeting `/api/provider-events/google/gmail` with OIDC authentication. Set `GOOGLE_PUBSUB_AUDIENCE` to that exact callback URL and `GOOGLE_PUBSUB_SERVICE_ACCOUNT` to the push service-account email. The endpoint verifies the Google-signed OIDC token.

For Microsoft Graph, register `PUBLIC_BASE_URL/api/provider-events/microsoft` as the notification URL. The app handles Graph's validation handshake and verifies each notification's `clientState`. For Google Drive, the app creates and renews change channels using `/api/provider-events/google/drive`.

Create a subscription while authenticated:

```http
POST /api/provider-events/subscriptions
Content-Type: application/json
Authorization: Bearer <access-token>

{"workflow_id":"<workflow-id>","provider":"google_gmail"}
```

Use `google_drive` for Drive changes, or `microsoft` with resource `me/messages` or `me/drive/root`. The workflow must be active and contain a webhook-compatible trigger block. Notifications enqueue workflow runs; Gmail/Drive notifications carry change cursors/metadata, and downstream blocks should fetch the corresponding current data. Provider subscription creation requires real OAuth connections and public HTTPS callback URLs. Reconnect provider accounts if permissions need updating.

## Worker recovery

Queued runs use database leases, heartbeat renewal, bounded retries and exponential backoff. A run interrupted while a node was actively executing is marked failed for review instead of being replayed automatically: an external write may have succeeded immediately before the crash, so blind replay could duplicate an email or file. Runs interrupted between nodes can be re-queued from completed step records.

For an existing database, back up first. For a v0.3 database, start the updated API once to create the new base tables, then apply `0002_multi_user_ownership.sql` exactly once. Apply `0003_worker_leases.sql` and `0004_provider_subscriptions.sql` exactly once, in that order. Migration 0004 is safe if the new subscription table was already created by startup. Fresh databases create the current schema automatically.

## Tests and build

```bash
pytest backend/tests -q
cd frontend
npm install
npm run build
```

GitHub Actions runs these backend and frontend checks on pushes and pull requests.

## Existing database upgrade

For an existing v0.3 SQLite database, make a backup, start the updated API once so new tables are created, then apply `backend/migrations/0002_multi_user_ownership.sql` exactly once. Do not run that migration on a fresh database. Existing rows without an owner remain inaccessible until explicitly transferred.

## Security and production status

This is a development foundation, not a production-ready hosted service. Before public deployment, add rate limiting, email verification and recovery, hardened session storage/rotation, audit events, worker leases and crash recovery, retry/dead-letter handling, monitoring, backups and a production database such as PostgreSQL. Do not expose the development server directly to the public internet. External write actions pause for human approval. File deletion is not implemented. See [Backend workflows](docs/BACKEND_WORKFLOWS.md) and [Security](docs/SECURITY.md).
