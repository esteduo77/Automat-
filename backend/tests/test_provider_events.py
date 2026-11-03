"""Smoke tests for native event route registration and durable queue schema."""

def test_native_provider_event_routes_are_registered():
    from backend.app.main import app

    paths = {route.path for route in app.routes}
    assert "/api/provider-events/subscriptions" in paths
    assert "/api/provider-events/microsoft" in paths
    assert "/api/provider-events/google/gmail" in paths
    assert "/api/provider-events/google/drive" in paths


def test_workflow_run_has_durable_lease_columns():
    from backend.app.models import WorkflowRun

    columns = set(WorkflowRun.__table__.columns.keys())
    assert {
        "worker_id",
        "lease_expires_at",
        "attempts",
        "max_attempts",
        "available_at",
        "last_error",
    }.issubset(columns)


def test_provider_subscription_has_expiry_and_callback_state():
    from backend.app.models import ProviderSubscription

    columns = set(ProviderSubscription.__table__.columns.keys())
    assert {"subscription_id", "client_state", "expires_at", "resource_id"}.issubset(columns)
