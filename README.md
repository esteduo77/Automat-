# Automation Hub

Automation Hub is a web-based visual automation workspace built with React, FastAPI, SQLite/SQLAlchemy, and OpenAI.

## Current foundation

- Visual React Flow canvas with categorized blocks and per-block settings.
- Workflow persistence, version counters, and immutable graph snapshots per execution.
- Backend graph validation and sequential execution with IF/ELSE branches.
- OpenAI text-analysis/summarization nodes using a server-side API key.
- Human approval nodes, pause/resume decisions, and run history.
- Google and Microsoft OAuth authorization-code + PKCE, encrypted token storage, and refresh-token renewal.
- Read-only Google Gmail search and Drive file search blocks.
- Read-only Microsoft Outlook message search and OneDrive file search blocks.
- Database-backed queued workflow runs and interval-based schedules.

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

Open the frontend at the Vite URL and API docs at http://localhost:8000/docs. Copy `.env.example` to `.env`. Never commit real credentials.

## Important limitations

This is a local-development foundation, not a production-ready multi-user service. There is no user authentication or tenancy, so do not expose it publicly. Provider blocks are read-only; sending email, modifying or deleting files, and other external side effects are deliberately not enabled. The built-in worker and scheduler run inside one API process and use the configured database; use exactly one API process until distributed job claiming/locking is implemented. A process outage pauses queued work and schedules until restart. Webhook/event-based triggers, durable distributed workers, retry policies, audit-event storage, and production deployment controls remain future work.

See [Architecture](docs/ARCHITECTURE.md), [Workflow editor](docs/WORKFLOW_EDITOR.md), [Backend workflows](docs/BACKEND_WORKFLOWS.md), and [Security](docs/SECURITY.md).
