import asyncio
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.models import Workflow, WorkflowRun
from backend.app.services.workflow_engine import execute_run, validate_graph, topological_order

def make_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()

def test_rejects_unknown_edge_endpoint():
    graph = {"nodes": [{"id": "start", "data": {"category": "Déclencheurs"}}], "edges": [{"source": "missing", "target": "start"}]}
    assert any("inexistant" in error for error in validate_graph(graph))

def test_topological_order_rejects_cycles():
    nodes = [{"id": "a"}, {"id": "b"}]
    edges = [{"source": "a", "target": "b"}, {"source": "b", "target": "a"}]
    try:
        topological_order(nodes, edges)
        assert False, "A cycle should be rejected"
    except ValueError as exc:
        assert "cycle" in str(exc)

def test_if_else_executes_only_matching_branch():
    db = make_session()
    graph = {
        "name": "Condition demo",
        "nodes": [
            {"id": "start", "data": {"category": "Déclencheurs", "label": "Déclencheur manuel"}},
            {"id": "if", "data": {"category": "Conditions", "label": "Condition si / sinon", "config": {"field": "score", "operator": "equals", "value": 10}}},
            {"id": "yes", "data": {"category": "Sorties", "label": "Afficher résultat"}},
            {"id": "no", "data": {"category": "Sorties", "label": "Afficher résultat"}},
        ],
        "edges": [
            {"source": "start", "target": "if"},
            {"source": "if", "sourceHandle": "true", "target": "yes"},
            {"source": "if", "sourceHandle": "false", "target": "no"},
        ],
    }
    workflow = Workflow(id=str(uuid4()), name="Condition demo", graph=graph)
    run = WorkflowRun(id=str(uuid4()), workflow_id=workflow.id, workflow_version=1, status="running", input_data={"score": 10})
    db.add_all([workflow, run]); db.commit()
    result = asyncio.run(execute_run(db, run, workflow))
    assert result.status == "completed"
    completed_ids = {step.node_id for step in result.steps if step.status == "completed"}
    assert {"start", "if", "yes"}.issubset(completed_ids)
    assert "no" not in completed_ids
    db.close()

def test_approval_node_pauses_run():
    db = make_session()
    graph = {
        "name": "Approval demo",
        "nodes": [
            {"id": "start", "data": {"category": "Déclencheurs", "label": "Déclencheur manuel"}},
            {"id": "approval", "data": {"category": "Validation", "label": "Validation humaine"}},
            {"id": "end", "data": {"category": "Sorties", "label": "Afficher résultat"}},
        ],
        "edges": [{"source": "start", "target": "approval"}, {"source": "approval", "target": "end"}],
    }
    workflow = Workflow(id=str(uuid4()), name="Approval demo", graph=graph)
    run = WorkflowRun(id=str(uuid4()), workflow_id=workflow.id, workflow_version=1, status="running", input_data={})
    db.add_all([workflow, run]); db.commit()
    result = asyncio.run(execute_run(db, run, workflow))
    assert result.status == "waiting_approval"
    assert any(step.status == "waiting_approval" for step in result.steps)
    db.close()
