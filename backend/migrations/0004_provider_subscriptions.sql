-- Persistent native provider notification subscriptions.
CREATE TABLE provider_subscriptions (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES users(id),
    workflow_id VARCHAR(36) NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    provider VARCHAR(32) NOT NULL,
    resource VARCHAR(200) NOT NULL,
    subscription_id VARCHAR(200) NOT NULL UNIQUE,
    client_state VARCHAR(128) NOT NULL,
    expires_at DATETIME,
    cursor TEXT,
    enabled BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME
);
CREATE INDEX IF NOT EXISTS ix_provider_subscriptions_user_id ON provider_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS ix_provider_subscriptions_workflow_id ON provider_subscriptions(workflow_id);
CREATE INDEX IF NOT EXISTS ix_provider_subscriptions_provider ON provider_subscriptions(provider);
CREATE INDEX IF NOT EXISTS ix_provider_subscriptions_expires_at ON provider_subscriptions(expires_at);
CREATE INDEX IF NOT EXISTS ix_provider_subscriptions_enabled ON provider_subscriptions(enabled);
