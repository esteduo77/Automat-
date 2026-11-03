# Automation Hub

Automation Hub is a web-based workflow automation workspace built with React, FastAPI, SQLAlchemy, and OpenAI.

## Implemented foundation

- Visual React Flow editor, workflow persistence, graph validation and IF/ELSE.
- User registration/login with Argon2 password hashing and JWT bearer tokens.
- User-owned workflows, per-user OAuth connections, and scoped run/schedule APIs.
- Google Gmail/Drive and Microsoft Outlook/OneDrive read operations.
- Approved write operations: send email, create/update cloud files. Each write node pauses for server-side human approval regardless of its UI policy setting.
- Database-backed queue processed by a separate worker process.
- Interval schedules and signed generic webhook endpoints.
- Encrypted OAuth tokens and webhook signing secrets.

## Local development

Copy `.env.example` to `.env`, then configure a unique `JWT_SECRET`, `OAUTH_ENCRYPTION_KEY`, and provider credentials as needed. Never commit secrets.

Backend API (repository root):

```bash
python -m venv .venv
# Activate the environment
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

In a second terminal, start the worker:

```bash
python -m backend.app.worker
```

In a third terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL; API docs are at http://localhost:8000/docs. Create an account in the UI before using workflows or connecting Google/Microsoft.

## Existing database upgrade

For an existing v0.3 SQLite database, back it up, start the updated API once so new tables are created, then apply `backend/migrations/0002_multi_user_ownership.sql` exactly once. Existing unowned records remain inaccessible until an administrator performs an explicit ownership transfer. A brand-new database does not need this SQL migration.

## Event triggers

The signed generic webhook trigger is available. Create a workflow containing a `Déclencheur webhook` block, save it, then use the editor's **Créer webhook** action. The signing secret is displayed once. Send JSON with an `X-Automation-Signature: sha256=...` HMAC-SHA256 header. Native Google Pub/Sub/Gmail Watch and Microsoft Graph subscription provisioning/renewal are not yet included.

## Important limitations

This is a development foundation, not a production-ready service. Add rate limiting, email verification/password recovery, stronger session management, audit events, worker leases/recovery, retries/dead-letter handling, and operational monitoring before public deployment. The worker uses atomic database compare-and-set claims; use PostgreSQL for multi-worker deployments. SQLite is for local development. A worker crash during a running task may require manual recovery. File deletion is not implemented. See [Backend workflows](docs/BACKEND_WORKFLOWS.md) and [Security](docs/SECURITY.md).
