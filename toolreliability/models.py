from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class ExpectedCall(BaseModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class Scenario(BaseModel):
    id: str
    name: str
    prompt: str
    expected_calls: list[ExpectedCall]
    forbidden_tools: list[str] = Field(default_factory=list)
    initial_state: dict[str, Any] = Field(default_factory=dict)
    expected_state: dict[str, Any] = Field(default_factory=dict)
    fault: dict[str, Any] | None = None
    max_tool_calls: int = 8


class ToolCall(BaseModel):
    tool: str
    arguments: dict[str, Any]
    success: bool = True
    error: str | None = None
    latency_ms: float = 0


class AgentResult(BaseModel):
    final_answer: str
    calls: list[ToolCall]
    final_state: dict[str, Any]
    latency_ms: float
    estimated_cost: float = 0


class Scores(BaseModel):
    tool_selection: float
    argument_accuracy: float
    sequence: float
    task_completion: float
    efficiency: float
    overall: float


class CaseResult(BaseModel):
    scenario_id: str
    scenario_name: str
    status: Literal["passed", "failed", "critical_failure"]
    scores: Scores
    agent_result: AgentResult
    failures: list[str] = Field(default_factory=list)


class RunSummary(BaseModel):
    run_id: str
    agent: str
    total: int
    passed: int
    pass_rate: float
    average_score: float
    p95_latency_ms: float
    cost_per_success: float
    results: list[CaseResult]

