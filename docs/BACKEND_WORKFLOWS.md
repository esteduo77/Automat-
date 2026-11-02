# Backend workflow engine and integrations

## Local setup

1. Create a virtual environment and install dependencies with `pip install -r requirements.txt`.
2. Copy `.env.example` to `.env`; keep real credentials private and out of Git.
3. Run `uvicorn backend.app.main:app --reload` from the repository root.
4. Open `http://localhost:8000/docs` for the API reference.

SQLite tables are created automatically on first API startup. Set `DATABASE_URL` to a managed database URL when moving beyond local development.

## Workflow API

- `POST /api/workflows` creates a draft from a React Flow graph.
- `GET /api/workflows` lists workflows.
- `PUT /api/workflows/{id}` updates a draft and increments its version.
- `POST /api/workflows/{id}/validate` checks the graph.
- `POST /api/workflows/{id}/activate` activates a validated graph.
- `POST /api/workflows/{id}/runs` starts a manual run.
- `GET /api/workflows/{id}/runs` and `GET /api/workflows/runs/{run_id}` expose run history.
- `POST /api/workflows/approvals/{approval_id}/decision` resumes or rejects a paused run.

The initial engine supports manual triggers, OpenAI text analysis/summarization, IF/ELSE branches, approval gates, data pass-through, and result nodes. Cycles are rejected. External side-effect blocks are not enabled.

## OpenAI

Set `OPENAI_API_KEY` and optionally `OPENAI_MODEL` in the server environment. The browser never receives the key. AI blocks fail clearly if the key is absent. Avoid sending private or sensitive data unless the user has permission and understands provider data handling.

## Google and Microsoft OAuth

Register these callback URLs in the provider developer portals:
- `http://localhost:8000/api/integrations/google/callback`
- `http://localhost:8000/api/integrations/microsoft/callback`

Set client IDs and secrets in `.env`, never in frontend code or Git. Generate a Fernet key with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` and set it as `OAUTH_ENCRYPTION_KEY`.

The integration API uses authorization code flow with PKCE, encrypts tokens at rest, and exposes connection status/disconnect endpoints. Initial scopes are read-only. Provider app registration, consent, redirect URI setup, and a reachable callback are required. Token refresh and actual Gmail/Drive/Graph workflow blocks are not yet wired into the workflow engine.

Do not expose this prototype publicly. Authentication, per-user tenancy, session CSRF protections, secret rotation, and production-grade token lifecycle management are required before deployment.
