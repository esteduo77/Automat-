# Architecture — Automation Hub v1

## Goals
Deliver a small, understandable foundation that can grow into a user-controlled automation platform.

## Components
- **Web client:** React + TypeScript + Vite; it displays system status and will become the control panel.
- **API:** Python + FastAPI; privileged operations and provider credentials stay on the server.
- **AI adapter:** OpenAI Python SDK behind an integration boundary. The key is read from the server environment and is never sent to the browser.
- **Provider adapters:** isolated modules for Google APIs and Microsoft Graph. They are placeholders in v1; OAuth flows and least-privilege scopes are future work.
- **Persistence:** database URL is configurable. Durable job history and user preferences are a later milestone.

## Request flow
1. The browser sends a request to the FastAPI API.
2. The API validates the request and checks permissions.
3. An automation service may ask the OpenAI adapter to interpret or plan the task.
4. The service returns a proposed action.
5. Sensitive operations require explicit user approval before execution.
6. The result is recorded for auditability (audit storage is planned, not yet implemented).

## Initial API
- GET / — service metadata
- GET /api/health — health check

OpenAPI documentation is available at /docs when the backend is running locally.

## Planned milestones
1. Add structured automation/job models and audit events.
2. Add OpenAI task planning with strict structured outputs and bounded tools.
3. Add human approval workflow.
4. Add Google OAuth and Gmail/Drive/Calendar adapters.
5. Add Microsoft OAuth and Graph adapters.
6. Add persistence, job history, and dashboard controls.
7. Add background execution and scheduling.

## Deliberate v1 limits
No email sending, file deletion, external account access, or background actions are enabled yet. The initial dashboard is a starter UI, not a finished automation console.
