# Security baseline

- Never commit `.env`, API keys, OAuth secrets, refresh tokens, or user data.
- Keep provider credentials and tokens on the backend; never expose them through frontend environment variables.
- Use `.env.example` only for empty placeholders and safe defaults.
- Request the minimum OAuth scopes needed for each feature and reconnect after scope changes.
- Require explicit confirmation before sending messages, deleting or overwriting files, or triggering consequential actions. Such write actions are not enabled in the current provider nodes.
- Validate and authorize every API request on the server.
- Avoid logging access tokens, secrets, message bodies, or file contents.
- Add durable audit records for proposed, approved, rejected, and executed actions before enabling real external side effects.
- Rotate any credential immediately if it is accidentally exposed.

The current OAuth flow uses authorization code + PKCE, encrypts tokens at rest with Fernet, and refreshes expiring access tokens when a refresh token is available. The current integration blocks are read-only. The prototype stores one connection per provider and has no user authentication or multi-user tenancy; do not expose it publicly.

The built-in queue and interval scheduler run in the API process. Use exactly one API process until atomic distributed job claiming/locking is implemented. A restart pauses processing while offline; queued jobs and schedule definitions remain in the database. This is not yet a high-availability worker system.

The API binds to loopback by default for local development. The Dockerfile binds inside the container to 0.0.0.0, so deployments must add authentication, authorization, CSRF/session protections, per-user data isolation, secret rotation, rate limiting, and operational controls first.
