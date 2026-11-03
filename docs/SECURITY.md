# Security baseline

- Never commit `.env`, JWT secrets, API keys, OAuth client secrets, refresh tokens, webhook secrets or user data.
- Set a unique random `JWT_SECRET` of at least 32 characters. Production mode rejects the example placeholder.
- Set `OAUTH_ENCRYPTION_KEY` to a Fernet key. OAuth tokens and webhook signing secrets are encrypted at rest.
- Passwords are hashed using Argon2. API endpoints for workflows, runs, approvals, schedules, OAuth connection management and webhook creation require a bearer token.
- Every workflow/run/schedule query is scoped to the authenticated user. OAuth state binds a callback to the initiating account. Webhook delivery uses a high-entropy secret and HMAC-SHA256 verification.
- OAuth scopes are limited to required read/send/file operations. Reconnect Google and Microsoft after the scope expansion.
- Sending mail and creating/updating cloud files always pause for server-side human approval. The UI policy cannot disable this gate. File deletion is not implemented.
- Do not log tokens, passwords, signing secrets, message bodies or file contents.

## Known gaps

This is not production-ready authentication: there is no email verification, password reset, MFA, rate limiting, refresh-token rotation/revocation or account recovery. Add those before public use. The frontend stores the access JWT in local storage; consider a reviewed HttpOnly-cookie/session design with CSRF protection for production.

The independent worker uses atomic database status updates to avoid duplicate claims. SQLite is for local use; use PostgreSQL for concurrent workers. Worker leases, crash recovery, retries, dead-letter handling and durable audit records are not yet implemented. Monitor worker processes and recover any runs left in `running` after a crash.

The generic webhook endpoint verifies HMAC signatures and stores encrypted secrets. Native Google Pub/Sub/Gmail Watch and Microsoft Graph subscription lifecycle support is not yet implemented. Webhook endpoints must be reachable over HTTPS in any hosted deployment.

Back up existing databases before applying schema changes. For an existing v0.3 SQLite database, run the documented one-time ownership migration. Old unowned records are not automatically assigned to any account.

Do not deploy publicly until the remaining gaps are addressed, a full security review is completed, and automated tests/builds pass.
