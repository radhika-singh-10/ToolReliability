from __future__ import annotations

import time
from typing import Protocol

from .models import AgentResult, Scenario, ToolCall
from .tools import ToolEnvironment


class AgentAdapter(Protocol):
    name: str
    async def run(self, scenario: Scenario, environment: ToolEnvironment) -> AgentResult: ...


class ReferenceCommerceAgent:
    """Reproducible reference adapter. Replace with any LLM or agent endpoint."""

    name = "reference-commerce-agent"

    async def run(self, scenario: Scenario, environment: ToolEnvironment) -> AgentResult:
        started = time.perf_counter()
        calls: list[ToolCall] = []
        for expected in scenario.expected_calls:
            success, _, error, latency = await environment.execute(expected.tool, expected.arguments)
            calls.append(ToolCall(tool=expected.tool, arguments=expected.arguments, success=success, error=error, latency_ms=latency))
            if not success and error == "timeout":
                success, _, error, latency = await environment.execute(expected.tool, expected.arguments)
                calls.append(ToolCall(tool=expected.tool, arguments=expected.arguments, success=success, error=error, latency_ms=latency))
            if not success:
                break
        return AgentResult(
            final_answer="Request completed." if all(c.success for c in calls) else "Request could not be completed.",
            calls=calls,
            final_state=environment.state,
            latency_ms=(time.perf_counter() - started) * 1000,
            estimated_cost=0.001 * len(calls),
        )


class RegressionAgent(ReferenceCommerceAgent):
    """Demo candidate that introduces a realistic wrong-tool regression."""

    name = "regression-demo-agent"

    async def run(self, scenario: Scenario, environment: ToolEnvironment) -> AgentResult:
        mutated = scenario.model_copy(deep=True)
        if "refund" in scenario.id:
            mutated.expected_calls = [c for c in mutated.expected_calls if c.tool != "refund.check_eligibility"]
        return await super().run(mutated, environment)

