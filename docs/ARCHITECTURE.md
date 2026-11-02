# Architecture — Automation Hub v1

## Goals
Deliver a small, understandable foundation that can grow into a user-controlled automation platform.

## Components
- **Web client:** React + TypeScript + Vite; the control panel will include a visual workflow editor.
- **Workflow editor:** free-form canvas with draggable nodes and typed connections; a categorized block library; a per-block configuration inspector.
- **API:** Python + FastAPI; privileged operations and provider credentials stay on the server.
- **Workflow service and engine (planned):** validate graph definitions, version workflows, schedule node execution, pause for approvals, and record run state.
- **AI adapter:** OpenAI Python SDK behind an integration boundary. The key is read from the server environment and is never sent to the browser.
- **Provider adapters:** isolated modules for Google APIs and Microsoft Graph. They are placeholders in v1; OAuth flows and least-privilege scopes are future work.
- **Persistence:** planned storage for workflows, immutable versions, runs, node runs, approvals, and audit events.

## Workflow editor decisions
- **Canvas:** a node-based free-form editor, with React Flow (@xyflow/react) recommended for the frontend.
- **Categories:** Triggers, AI, Google, Microsoft, Files & data, Conditions, Approvals, and Outputs.
- **Execution policy:** configurable on each block (always, on_risk, or never), subject to server-enforced minimum approval requirements. Enabling a workflow does not pre-approve future sensitive actions.
- **Execution model:** start with deterministic sequential execution and conditional branches; defer loops, parallel execution, and sub-workflows.

The detailed design, data model, API proposal, safety rules, and delivery plan are documented in [WORKFLOW_EDITOR.md](./WORKFLOW_EDITOR.md).

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
1. Build the categorized visual canvas and block inspector.
2. Add workflow graph models, validation, versioning, and persistence.
3. Add a deterministic execution engine, run history, and per-block approval gates.
4. Add safe AI blocks and structured outputs.
5. Add Google OAuth and Gmail/Drive/Calendar adapters.
6. Add Microsoft OAuth and Graph adapters.
7. Add background execution, scheduling, and operational controls.

## Deliberate v1 limits
No email sending, file deletion, external account access, or background actions are enabled yet. The visual workflow editor frontend is a first interactive prototype. Workflow persistence on the server, the execution engine, approval APIs, and provider integrations are not implemented yet.
