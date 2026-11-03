# Backend workflow engine and integrations

## Local setup

1. Create a virtual environment and install dependencies with `pip install -r requirements.txt`.
2. Copy `.env.example` to `.env`; keep real credentials private and out of Git.
3. Run `uvicorn backend.app.main:app --reload` from the repository root.
4. Open `http://localhost:8000/docs` for the API reference.

SQLite tables are created automatically on first API startup. Set `DATABASE_URL` to a managed database URL beyond local development. `create_all` creates new tables but does not perform general schema migrations. Back up the database before changing model schemas.

## Workflow and queue API

- `POST /api/workflows` creates a draft from a React Flow graph.
- `GET /api/workflows` lists workflows.
- `PUT /api/workflows/{id}` updates a draft and increments its version.
- `POST /api/workflows/{id}/validate` checks the graph.
- `POST /api/workflows/{id}/activate` activates a validated graph.
- `POST /api/workflows/{id}/runs` places a manual run in the database-backed queue and returns HTTP 202.
- `GET /api/workflows/{id}/runs` and `GET /api/workflows/runs/{run_id}` expose run history.
- `POST /api/workflows/approvals/{approval_id}/decision` rejects a run or queues it to resume after approval.

The API lifespan starts a polling worker. It claims queued work in a single-process setup, executes workflow nodes, and stores step results. Keep exactly one API process: distributed locking/atomic job claiming is not implemented yet.

## Scheduled automations

- `POST /api/automations/workflows/{workflow_id}/schedule` with JSON `{"interval_seconds":300}` activates the workflow and creates a recurring interval schedule. Minimum interval: 60 seconds.
- `GET /api/automations` lists schedules.
- `POST /api/automations/{schedule_id}/pause` pauses a schedule.
- `POST /api/automations/{schedule_id}/resume` resumes it.

The worker enqueues due runs into the same database queue. This first scheduler is interval-based, not a full calendar/cron editor. If the process is offline, schedules are checked after restart; missed intervals are coalesced into one next run. Event/webhook triggers are not implemented.

## Google and Microsoft

Register these callback URLs in provider developer portals:
- `http://localhost:8000/api/integrations/google/callback`
- `http://localhost:8000/api/integrations/microsoft/callback`

Set client IDs and secrets in `.env`, never in frontend code or Git. Generate a Fernet key with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set the result as `OAUTH_ENCRYPTION_KEY`. Reconnect accounts after changing requested OAuth scopes so the consent grant includes them.

Implemented read-only workflow blocks:
- Google: Gmail message search (metadata and snippet) and Google Drive file search.
- Microsoft: Outlook message search and OneDrive file search.

OAuth uses authorization code + PKCE. Tokens are encrypted at rest; expiring access tokens are refreshed server-side when a refresh token is available. If a provider does not issue a refresh token, reconnect the account. Provider app registration, consent, exact redirect URI setup, and a reachable callback are required. The initial connection model supports one account per provider (single-user prototype).

## OpenAI

Set `OPENAI_API_KEY` and optionally `OPENAI_MODEL` in the server environment. The browser never receives the key. AI blocks fail clearly if the key is absent. Avoid sending private or sensitive data unless the user has permission and understands provider data handling.

## Production blockers

Do not expose this prototype publicly. Authentication, per-user tenancy, per-user OAuth token isolation, CSRF/session protections, distributed queue locking, retry/backoff, schedule ownership, webhook signature verification, audit records, secret rotation, and operational monitoring are required before production. External side-effect blocks (send email, modify/delete files) are intentionally not enabled.
