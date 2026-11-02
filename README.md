# Automation Hub

Automation Hub is a web-based visual automation workspace built with React, FastAPI, SQLite/SQLAlchemy, and OpenAI.

## Current foundation

- Visual React Flow canvas with categorized blocks and per-block settings.
- Workflow persistence, version counters, and immutable graph snapshots per execution.
- Backend graph validation and deterministic sequential execution with IF/ELSE branches.
- OpenAI text-analysis/summarization nodes using a server-side API key.
- Human approval nodes, pause/resume decisions, and run history.
- Google and Microsoft OAuth authorization-code + PKCE connection flow, with encrypted token storage and read-only initial scopes.

## Local development

Backend setup and OAuth configuration: see [Backend workflows](docs/BACKEND_WORKFLOWS.md).

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Backend (from repository root):

```bash
python -m venv .venv
# Activate the virtual environment, then:
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

Open the frontend at the Vite URL and the API docs at http://localhost:8000/docs. Copy `.env.example` to `.env` for local settings. Never commit real credentials.

## Important limitations

This is a local-development foundation, not a production-ready multi-user service. The API has no user authentication or tenancy yet. Do not expose it publicly. Google/Microsoft account connection is implemented, but provider-specific workflow actions, token refresh, and actual Gmail/Drive/Graph operations are not yet available. Scheduled triggers, durable background jobs, audit-event storage, and real external side effects are also future work. The current engine supports manual runs, IF/ELSE, AI text nodes, approval gates, and basic data/result nodes.

See [Architecture](docs/ARCHITECTURE.md), [Workflow editor](docs/WORKFLOW_EDITOR.md), [Backend workflows](docs/BACKEND_WORKFLOWS.md), and [Security](docs/SECURITY.md).
