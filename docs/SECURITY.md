# Security baseline

- Never commit `.env`, JWT secrets, API keys, OAuth client secrets, refresh tokens, webhook secrets or user data.
- Set a unique random `JWT_SECRET` of at least 32 characters. Production mode rejects the example placeholder.
- Set `OAUTH_ENCRYPTION_KEY` to a Fernet key. OAuth tokens and webhook signing secrets are encrypted at rest.
- Passwords are hashed using Argon2. API endpoints for workflows, runs, approvals, schedules, OAuth connection management and webhook creation require a bearer token.
- Every workflow/run/schedule query is scoped to the authenticated user. OAuth state binds a callback to the initiating account. Webhook delivery uses a high-entropy secret and HMAC-SHA256 verification.
- OAuth scopes are limited to required read/send/file operations. Reconnect Google and Microsoft after the scope expansion.
- Sending mail and creating/updating cloud files always pause for server-side human approval. The UI policy cannot disable this gate. File deletion is not implemented.
- Do not log tokens, passwords, signing secrets, message bodies or file contents.

## Additional protections in this branch

- Login and registration have per-IP request limits; API responses include baseline browser security headers.
- Production startup rejects placeholder JWT secrets, missing OAuth encryption keys, SQLite, and wildcard CORS.
- Worker leases and provider subscriptions are persisted in the database; provider callbacks validate Microsoft client state, Google Drive channel tokens, and Google Pub/Sub OIDC identity.
- Provider notifications are converted into queued runs only after matching a stored subscription and its owning workflow.

## Known gaps

This is still not production-ready authentication: email verification, password reset, MFA, account recovery, refresh-token rotation/revocation and HttpOnly cookie sessions with CSRF protection are not implemented. The current rate limiter is process-local and is not sufficient by itself for multi-instance production; enforce distributed limits at an API gateway or reverse proxy. The frontend stores access JWTs in local storage.

The worker uses database leases, heartbeats, bounded retries and stale-run recovery. A node left in-flight is failed for manual review because the outcome of an external side effect may be ambiguous. The retry queue is not a full dead-letter service, and there is no distributed worker dashboard yet. Use PostgreSQL for concurrent workers.

The generic webhook endpoint verifies HMAC signatures and stores encrypted secrets. Native Google Gmail/Drive and Microsoft Graph subscriptions are supported, but require provider-side Cloud Pub/Sub, OAuth permissions, HTTPS callback registration and valid external credentials. Validate renewals and event delivery against real provider test accounts before production.

Back up existing databases before applying schema changes. For an existing v0.3 SQLite database, run the documented one-time ownership migration. Old unowned records are not automatically assigned to any account.

Do not deploy publicly until the remaining gaps are addressed, a full security review is completed, and automated tests/builds pass.
