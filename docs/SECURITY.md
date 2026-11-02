# Security baseline

- Never commit .env, API keys, OAuth secrets, refresh tokens, or user data.
- Keep provider credentials on the backend; never expose them through frontend environment variables.
- Use .env.example only for empty placeholders and safe defaults.
- Request the minimum OAuth scopes needed for each feature.
- Require explicit confirmation before sending messages, deleting or overwriting files, or triggering consequential actions.
- Validate and authorize every API request on the server.
- Avoid logging access tokens, secrets, message bodies, or file contents.
- Add audit records for proposed, approved, rejected, and executed actions before enabling real automations.
- Rotate any credential immediately if it is accidentally exposed.

The current OAuth flow uses authorization code + PKCE and stores provider tokens encrypted at rest. Initial scopes are read-only. Provider workflow actions and token refresh are not implemented. The API binds to loopback by default for local development, but it has no user authentication or multi-user tenancy; do not expose it publicly. The Dockerfile binds inside the container to 0.0.0.0, so deployments must add authentication, authorization, CSRF/session protections, secret rotation, and operational controls first.
