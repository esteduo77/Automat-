import json
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy.orm import Session
from sqlalchemy import select
from backend.app.models import Approval, NodeRun, Workflow, WorkflowRun

def utcnow():
    return datetime.now(timezone.utc)

def block_kind(data: dict) -> str:
    explicit = data.get("block_type")
    if explicit:
        return str(explicit)
    label = str(data.get("label", "")).lower()
    category = str(data.get("category", "")).lower()
    if category in ("déclencheurs", "triggers"):
        return "trigger.webhook" if "webhook" in label else ("trigger.schedule" if "planifié" in label else "trigger.manual")
    if category == "ia" or "résum" in label or "analyser" in label or "classer" in label:
        return "ai.summarize" if "résum" in label else "ai.analyze"
    if category == "conditions" or "condition" in label:
        return "condition.if_else"
    if category == "validation" or "validation" in label:
        return "approval.manual"
    if category == "fichiers & données":
        return "data.transform"
    if category == "google":
        if "envoyer" in label: return "google.gmail.send"
        if "créer" in label: return "google.drive.create"
        if "modifier" in label: return "google.drive.update"
        return "google.gmail.search" if "e-mail" in label or "email" in label else "google.drive.search"
    if category == "microsoft":
        if "envoyer" in label: return "microsoft.mail.send"
        if "créer" in label: return "microsoft.drive.create"
        if "modifier" in label: return "microsoft.drive.update"
        return "microsoft.mail.search" if "message" in label or "e-mail" in label else "microsoft.drive.search"
    if category == "sorties":
        return "output.result"
    return "utility.noop"

def validate_graph(graph: dict) -> list[str]:
    nodes = graph.get("nodes", []); edges = graph.get("edges", [])
    ids = [node.get("id") for node in nodes]; errors = []
    if len(ids) != len(set(ids)):
        errors.append("Les identifiants des blocs doivent être uniques.")
    known = set(ids)
    for edge in edges:
        if edge.get("source") not in known or edge.get("target") not in known:
            errors.append("Une connexion référence un bloc inexistant.")
    if not errors:
        try: topological_order(nodes, edges)
        except ValueError as exc: errors.append(str(exc))
    if nodes and not any(block_kind(n.get("data", {})).startswith("trigger.") for n in nodes):
        errors.append("Le workflow doit contenir un déclencheur.")
    return errors

def topological_order(nodes: list[dict], edges: list[dict]) -> list[str]:
    node_ids = [n["id"] for n in nodes]; ids = set(node_ids)
    incoming = {node_id: 0 for node_id in node_ids}; outgoing = {node_id: [] for node_id in node_ids}
    for edge in edges:
        source, target = edge["source"], edge["target"]
        if source not in ids or target not in ids: raise ValueError("Connexion invalide.")
        outgoing[source].append(target); incoming[target] += 1
    queue = [node_id for node_id in node_ids if incoming[node_id] == 0]; order = []
    while queue:
        current = queue.pop(0); order.append(current)
        for target in outgoing[current]:
            incoming[target] -= 1
            if incoming[target] == 0: queue.append(target)
    if len(order) != len(ids):
        raise ValueError("Le workflow contient un cycle. Les cycles ne sont pas encore pris en charge.")
    return order

def _condition(config: dict, context: dict) -> bool:
    actual = context.get(str(config.get("field", "value"))); expected = config.get("value"); operator = config.get("operator", "equals")
    if operator == "equals": return actual == expected or (actual is not None and expected is not None and str(actual) == str(expected))
    if operator == "not_equals": return not (actual == expected or (actual is not None and expected is not None and str(actual) == str(expected)))
    if operator == "contains": return str(expected).lower() in str(actual or "").lower()
    if operator == "is_true": return bool(actual)
    if operator == "is_false": return not bool(actual)
    raise ValueError("Opérateur de condition non pris en charge.")

async def _ai_call(text: str, instruction: str) -> str:
    from backend.app.config import get_settings
    from backend.app.integrations.openai_client import get_openai_client
    settings = get_settings(); client = get_openai_client()
    try:
        response = await client.responses.create(model=settings.openai_model, instructions=instruction, input=text[:20000])
        return response.output_text
    finally:
        await client.close()

async def execute_run(db: Session, run: WorkflowRun, workflow: Workflow, approved_node_ids: set[str] | None = None) -> WorkflowRun:
    approved_node_ids = approved_node_ids or set()
    graph = run.graph_snapshot or workflow.graph
    nodes = graph.get("nodes", []); edges = graph.get("edges", [])
    errors = validate_graph(graph)
    if errors: raise ValueError(" ".join(errors))
    order = topological_order(nodes, edges); node_map = {node["id"]: node for node in nodes}
    completed = {step.node_id for step in run.steps if step.status == "completed"}
    context = dict(run.input_data or {})
    for step in run.steps:
        if step.status == "completed": context.update(step.output_data or {})
    active_nodes = set()
    for node_id in order:
        node = node_map[node_id]; data = node.get("data", {}); kind = block_kind(data)
        trigger_type = str((run.input_data or {}).get("_trigger_type", "manual"))
        if kind == "trigger.manual" and trigger_type == "manual": active_nodes.add(node_id)
        elif kind == "trigger.schedule" and trigger_type == "schedule": active_nodes.add(node_id)
        elif kind == "trigger.webhook" and trigger_type == "webhook": active_nodes.add(node_id)
        if node_id not in active_nodes: continue
        if node_id in completed:
            prior = next((item for item in run.steps if item.node_id == node_id and item.status == "completed"), None)
            prior_output = prior.output_data if prior else {}
            for edge in edges:
                if edge["source"] == node_id:
                    handle = edge.get("sourceHandle")
                    if kind != "condition.if_else" or handle in (("true", "yes") if prior_output.get("condition") else ("false", "no")):
                        active_nodes.add(edge["target"])
            continue
        config = data.get("config", {}); policy = data.get("policy", "on_risk")
        step = NodeRun(id=str(uuid4()), run_id=run.id, node_id=node_id, node_type=kind, status="running", input_data=context)
        db.add(step); db.commit()
        try:
            if kind == "trigger.manual":
                output = {"triggered": True}
            elif kind == "trigger.schedule":
                output = {"triggered": True, "scheduled": True}
            elif kind == "trigger.webhook":
                output = {"triggered": True, "event": context.get("event", {})}
            elif kind == "condition.if_else":
                result = _condition(config, context); output = {"condition": result, "branch": "true" if result else "false"}
            elif kind == "approval.manual":
                prior_approval = db.scalar(select(Approval).where(Approval.run_id == run.id,
                    Approval.node_id == node_id, Approval.status == "approved"))
                if policy != "never" and node_id not in approved_node_ids and not prior_approval:
                    step.status = "waiting_approval"
                    db.add(Approval(id=str(uuid4()), run_id=run.id, node_id=node_id,
                        summary=f"Validation requise pour le bloc « {data.get('label', kind)} »."))
                    run.status = "waiting_approval"; db.commit(); return run
                output = {"approved": policy == "never" or node_id in approved_node_ids or bool(prior_approval)}
            elif kind.startswith("ai."):
                prompt = str(config.get("prompt") or "Analyse le contenu fourni et retourne un résultat concis.")
                source = str(config.get("text") or context.get("text") or json.dumps(context, ensure_ascii=False))
                output = {"text": await _ai_call(source, prompt)}
            elif kind.startswith("google.") or kind.startswith("microsoft."):
                is_write = kind.endswith(".send") or kind.endswith(".create") or kind.endswith(".update")
                if is_write:
                    approved = db.scalar(select(Approval).where(Approval.run_id == run.id,
                        Approval.node_id == node_id, Approval.status == "approved"))
                    if not approved:
                        step.status = "waiting_approval"
                        db.add(Approval(id=str(uuid4()), run_id=run.id, node_id=node_id,
                            summary=f"Autoriser l’action externe « {data.get('label', kind)} » ?"))
                        run.status = "waiting_approval"; db.commit(); return run
                from backend.app.integrations.provider_clients import google_action, microsoft_action
                action = google_action if kind.startswith("google.") else microsoft_action
                output = await action(db, kind, config, context, workflow.owner_id)
                output = {"provider_result": output}
            elif kind == "data.transform":
                output = {"transformed": context}
            elif kind == "output.result":
                output = {"result": context}
            elif kind == "utility.noop":
                output = {"message": "Bloc de démonstration sans effet externe."}
            else:
                raise ValueError(f"Type de bloc inconnu : {kind}")
            step.output_data = output; step.status = "completed"; step.finished_at = utcnow()
            context.update(output); db.commit()
            for edge in edges:
                if edge["source"] == node_id:
                    handle = edge.get("sourceHandle")
                    if kind != "condition.if_else" or handle in (("true", "yes") if output.get("condition") else ("false", "no")):
                        active_nodes.add(edge["target"])
        except Exception as exc:
            step.status = "failed"; step.error = str(exc)[:2000]; step.finished_at = utcnow()
            run.status = "failed"; run.finished_at = utcnow(); db.commit(); return run
    run.output_data = context; run.status = "completed"; run.finished_at = utcnow(); db.commit()
    return run
