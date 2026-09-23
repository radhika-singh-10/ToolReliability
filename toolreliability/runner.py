from __future__ import annotations

import asyncio
import math
import uuid

from .agents import AgentAdapter
from .evaluator import evaluate
from .models import RunSummary, Scenario
from .tools import ToolEnvironment


async def run_suite(scenarios: list[Scenario], agent: AgentAdapter, concurrency: int = 8) -> RunSummary:
    semaphore = asyncio.Semaphore(concurrency)

    async def run_one(scenario: Scenario):
        async with semaphore:
            result = await agent.run(scenario, ToolEnvironment(scenario.initial_state, scenario.fault))
            return evaluate(scenario, result)

    results = await asyncio.gather(*(run_one(s) for s in scenarios))
    latencies = sorted(r.agent_result.latency_ms for r in results)
    p95_index = max(0, math.ceil(0.95 * len(latencies)) - 1)
    passed = sum(r.status == "passed" for r in results)
    total_cost = sum(r.agent_result.estimated_cost for r in results)
    return RunSummary(
        run_id=str(uuid.uuid4()), agent=agent.name, total=len(results), passed=passed,
        pass_rate=round(passed / len(results), 4),
        average_score=round(sum(r.scores.overall for r in results) / len(results), 4),
        p95_latency_ms=round(latencies[p95_index], 2),
        cost_per_success=round(total_cost / passed, 5) if passed else total_cost,
        results=results,
    )

