-- Upgrade an existing v0.3 SQLite database to multi-user ownership.
-- Back up automation_hub.db first. Run this once AFTER the updated app has created
-- the users and webhook_endpoints tables. Do not run on a brand-new database.
ALTER TABLE workflows ADD COLUMN owner_id VARCHAR(36) REFERENCES users(id);
CREATE INDEX IF NOT EXISTS ix_workflows_owner_id ON workflows(owner_id);
ALTER TABLE oauth_connections ADD COLUMN user_id VARCHAR(36) REFERENCES users(id);
CREATE INDEX IF NOT EXISTS ix_oauth_connections_user_id ON oauth_connections(user_id);
ALTER TABLE oauth_states ADD COLUMN user_id VARCHAR(36) REFERENCES users(id);
CREATE INDEX IF NOT EXISTS ix_oauth_states_user_id ON oauth_states(user_id);

-- Existing unowned workflows/connections are intentionally not assigned to a new user.
-- An administrator must perform an explicit, trusted data ownership transfer if needed.
