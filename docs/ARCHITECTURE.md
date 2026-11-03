# Architecture — Automation Hub v1

## Goals
A user-controlled automation platform with explicit permissions and traceable execution.

## Components
- **Web client:** React + TypeScript + Vite with a React Flow canvas and categorized block library.
- **API:** FastAPI with JWT authentication; workflows, runs, approvals, schedules and OAuth connections are scoped to the authenticated owner.
- **Workflow engine:** SQLAlchemy persistence, graph validation, versioned snapshots, deterministic sequential execution, IF/ELSE, approval pauses and run history.
- **Worker:** separate process (`python -m backend.app.worker`) polling a database queue. Conditional updates atomically claim runs and due schedules.
- **AI adapter:** OpenAI SDK; credentials remain server-side.
- **Provider adapters:** Google OAuth and Microsoft OAuth with per-user encrypted tokens; read/search plus approved send and text-file create/update operations.
- **Event ingress:** signed generic webhook endpoints. Provider-native Gmail Pub/Sub and Microsoft Graph subscription management are not yet implemented.
- **Persistence:** workflows, runs, node runs, approvals, OAuth state/connections, users, schedules and webhook endpoints.

## Execution and safety
- Every external write action (send email, create file, update file) requires a server-side approval record. The UI policy cannot bypass this gate.
- OAuth connections are isolated by user; the OAuth callback state is bound to the initiating account.
- Webhook signing secrets and OAuth tokens are encrypted at rest using Fernet.
- File deletion and other destructive actions are not enabled.
- A workflow is activated when its owner creates a schedule or webhook endpoint, after graph validation.

## Request flow
1. The browser authenticates and sends a bearer JWT.
2. The API scopes data access to the authenticated user.
3. Manual, scheduled or signed-webhook triggers enqueue an immutable workflow snapshot.
4. A separate worker atomically claims the run and executes it.
5. Sensitive write nodes pause for explicit human approval; the worker resumes and performs the operation only after approval.
6. Run and node results are persisted for history.

## Current limitations
This is a development foundation, not production-ready. Authentication still needs email verification, password recovery, rate limiting, refresh/revocation and MFA. The worker needs leases, crash recovery, retry/backoff, dead-letter handling and monitoring. Direct Google/Microsoft event subscription provisioning and renewal are not yet included. Automated test and frontend build verification are still required. Use PostgreSQL for concurrent deployments; SQLite is intended for local development.

See [WORKFLOW_EDITOR.md](./WORKFLOW_EDITOR.md), [BACKEND_WORKFLOWS.md](./BACKEND_WORKFLOWS.md), and [SECURITY.md](./SECURITY.md).
