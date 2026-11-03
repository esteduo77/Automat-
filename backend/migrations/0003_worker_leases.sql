-- Upgrade existing workflow_runs for lease-based worker recovery.
-- Back up the database first. Run exactly once on an existing database.
ALTER TABLE workflow_runs ADD COLUMN worker_id VARCHAR(64);
ALTER TABLE workflow_runs ADD COLUMN lease_expires_at DATETIME;
ALTER TABLE workflow_runs ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE workflow_runs ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 3;
ALTER TABLE workflow_runs ADD COLUMN available_at DATETIME;
ALTER TABLE workflow_runs ADD COLUMN last_error TEXT;
CREATE INDEX IF NOT EXISTS ix_workflow_runs_worker_id ON workflow_runs(worker_id);
CREATE INDEX IF NOT EXISTS ix_workflow_runs_lease_expires_at ON workflow_runs(lease_expires_at);
CREATE INDEX IF NOT EXISTS ix_workflow_runs_available_at ON workflow_runs(available_at);

-- Recover runs left in running state by the pre-lease worker.
UPDATE workflow_runs SET lease_expires_at = CURRENT_TIMESTAMP WHERE status = 'running' AND lease_expires_at IS NULL;
