# Backend workflows, integrations and workers

## Run locally

1. Copy `.env.example` to `.env`.
2. Set a unique `JWT_SECRET` (at least 32 random characters) and generate `OAUTH_ENCRYPTION_KEY` using the command below.
3. Install dependencies: `pip install -r requirements.txt`.
4. Start the API: `uvicorn backend.app.main:app --reload`.
5. Start the independent worker in another terminal: `python -m backend.app.worker`.
6. Start the frontend: `cd frontend && npm install && npm run dev`.

The API creates new tables on startup. SQLAlchemy `create_all` does not add columns to existing tables. For a pre-existing v0.3 SQLite database, back it up, start the new API once, then apply `backend/migrations/0002_multi_user_ownership.sql` exactly once. Do not apply this migration to a brand-new database. Existing unowned workflows and provider connections are intentionally not auto-assigned to the first registering account.

## Authentication and tenant isolation

- `POST /api/auth/register` creates an account (12-character minimum password).
- `POST /api/auth/login` returns a JWT bearer token.
- `GET /api/auth/me` returns the authenticated account.
- The frontend stores the bearer token in local storage and attaches it to authenticated API calls.
- Workflow CRUD, runs, approvals, schedules, OAuth connections and webhook creation are scoped to the authenticated user.
- OAuth callback state is bound to the user who initiated the connection.
- OAuth tokens and webhook signing secrets are encrypted at rest with Fernet.

This is a first authentication layer, not a complete public identity system: add rate limits, email verification, password reset, refresh/revocation, MFA and security review before production.

## Separate worker and queue

Run the worker independently with `python -m backend.app.worker`; the API no longer starts its own worker loop. The worker polls the database queue and schedule table. A conditional status update atomically claims a queued run, preventing two workers from claiming the same run simultaneously. PostgreSQL is recommended for multi-worker deployments; SQLite is intended for local development.

The worker executes the workflow engine and persists step/run state. A process crash after claiming a run can leave it in `running`; lease expiry, automatic recovery, retries and dead-letter handling remain to be implemented. Keep worker processes supervised and monitor their logs.

## Scheduled workflows

- `POST /api/automations/workflows/{workflow_id}/schedule` with `{"interval_seconds":300}`.
- `GET /api/automations` lists only the current user's schedules.
- `POST /api/automations/{schedule_id}/pause` and `resume` control owned schedules.

Minimum interval is 60 seconds. This is an interval scheduler, not a cron/calendar editor.

## Signed webhook triggers

Add a `Déclencheur webhook` node to a workflow, save it, and use **Créer webhook** in the editor. The endpoint is activated and the API returns a URL path plus a signing secret (shown once). The caller sends the raw JSON request body and header:

```
X-Automation-Signature: sha256=<hex HMAC-SHA256(secret, raw_request_body)>
```

POST to `/api/webhooks/{endpoint_id}`. The signature is checked with constant-time comparison; webhook secrets are encrypted at rest. The event JSON is made available to the workflow as `event` in its input context.

This generic signed ingress can receive events from an external service or relay. Direct Gmail Watch/Pub/Sub and Microsoft Graph subscription provisioning, validation, renewal and provider-specific notification parsing are not yet implemented.

## Google and Microsoft actions

OAuth callback URLs:
- `http://localhost:8000/api/integrations/google/callback`
- `http://localhost:8000/api/integrations/microsoft/callback`

Google scopes include Gmail read/send and Drive metadata/file operations. Microsoft scopes include basic mail read, Mail.Send and Files.ReadWrite. Reconnect accounts after granting the expanded scopes. Tokens are encrypted at rest and refreshed server-side when a refresh token exists.

Read nodes search Gmail, Drive, Outlook and OneDrive. Write nodes include sending mail and creating/updating text files. The engine always creates a pending approval for every write node; the approval must be explicitly accepted before the operation is executed. The editor's per-node policy cannot bypass this server-side gate. File deletion is not provided.

## OpenAI

Set `OPENAI_API_KEY` and optionally `OPENAI_MODEL` in the server environment. The key remains server-side.

## Production requirements

Do not expose this project publicly yet. It still needs comprehensive automated tests, migration management, rate limiting, email verification, password recovery, token revocation, CSRF strategy if cookie auth is introduced, audit logs, worker leases/recovery, retries, monitoring, webhook provider adapters, and deployment hardening.
