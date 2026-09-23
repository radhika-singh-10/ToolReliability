from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any

from .domain_tools import DomainEnvironment, environment_for
from .evaluator import evaluate
from .models import AgentResult, CaseResult, RunSummary, Scenario, ToolCall


@dataclass(frozen=True)
class HarnessPolicy:
    concurrency: int = 8
    max_attempts: int = 2
    case_timeout_seconds: float = 30
    minimum_pass_rate: float = 0.85


class OrchestratorAgent:
    """Policy-controlled planner/executor whose planner can be replaced by an LLM."""

    name = "orchestrator-agent"

    def __init__(self, max_attempts: int = 2):
        self.max_attempts = max_attempts

    async def run(self, scenario: Scenario, environment: DomainEnvironment) -> AgentResult:
        started = time.perf_counter()
        trace: list[ToolCall] = []
        for planned in scenario.expected_calls:
            for _ in range(self.max_attempts):
                try:
                    success, response, error, latency, attempt = await environment.execute(planned.tool, planned.arguments)
                except ValueError as exc:
                    success, response, error, latency = False, {}, str(exc), 0
                    attempt = environment.attempts.get(planned.tool, 1)
                trace.append(ToolCall(tool=planned.tool, arguments=planned.arguments, success=success,
                                      response=response, error=error, latency_ms=latency, attempt=attempt))
                if success:
                    break
                if error not in {"timeout", "rate_limit", "connection_reset"}:
                    break
            if not trace[-1].success:
                break
        succeeded = all(any(call.tool == step.tool and call.success for call in trace) for step in scenario.expected_calls)
        return AgentResult(
            final_answer="Workflow completed and verified." if succeeded else "Workflow stopped after a tool failure.",
            calls=trace, final_state=environment.state,
            latency_ms=(time.perf_counter() - started) * 1000,
            estimated_cost=round(0.0005 * len(trace), 6),
        )


class EvaluationHarness:
    def __init__(self, policy: HarnessPolicy | None = None, store: Any | None = None):
        self.policy = policy or HarnessPolicy()
        self.store = store

    async def execute(self, scenarios: list[Scenario], agent: OrchestratorAgent | None = None) -> RunSummary:
        agent = agent or OrchestratorAgent(self.policy.max_attempts)
        semaphore = asyncio.Semaphore(self.policy.concurrency)

        async def execute_case(scenario: Scenario) -> CaseResult:
            async with semaphore:
                environment = environment_for(scenario.domain, scenario.initial_state, scenario.fault)
                result = await asyncio.wait_for(agent.run(scenario, environment), self.policy.case_timeout_seconds)
                return evaluate(scenario, result)

        results = await asyncio.gather(*(execute_case(s) for s in scenarios))
        latencies = sorted(item.agent_result.latency_ms for item in results)
        p95 = latencies[max(0, int(0.95 * len(latencies)) - 1)]
        passed = sum(item.status == "passed" for item in results)
        total_cost = sum(item.agent_result.estimated_cost for item in results)
        summary = RunSummary(
            run_id=str(uuid.uuid4()), agent=agent.name, total=len(results), passed=passed,
            pass_rate=round(passed / len(results), 4),
            average_score=round(sum(item.scores.overall for item in results) / len(results), 4),
            p95_latency_ms=round(p95, 2),
            cost_per_success=round(total_cost / passed, 6) if passed else total_cost,
            results=results,
        )
        if self.store:
            self.store.save_run(summary, domains=sorted({s.domain for s in scenarios}))
        return summary
