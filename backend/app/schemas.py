from typing import Any, Literal
from pydantic import BaseModel, Field

class WorkflowNode(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    type: str = "hub"
    position: dict[str, float] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)

class WorkflowEdge(BaseModel):
    id: str | None = None
    source: str
    target: str
    sourceHandle: str | None = None
    targetHandle: str | None = None

class WorkflowGraph(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    nodes: list[WorkflowNode] = Field(min_length=1, max_length=100)
    edges: list[WorkflowEdge] = Field(default_factory=list, max_length=300)

class RunRequest(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)

class ApprovalDecision(BaseModel):
    decision: Literal["approve", "reject"]
    comment: str | None = Field(default=None, max_length=1000)
