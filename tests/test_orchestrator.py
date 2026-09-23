import asyncio
from pathlib import Path

from toolreliability.orchestrator import EvaluationHarness, HarnessPolicy
from toolreliability.scenarios import load_domain
from toolreliability.storage import RunStore


def test_data_analytics_harness(tmp_path: Path):
    store = RunStore(tmp_path / "runs.db")
    summary = asyncio.run(EvaluationHarness(HarnessPolicy(concurrency=2), store).execute(load_domain("data_analytics")))
    assert summary.pass_rate == 1.0
    assert len(store.list_runs()) == 1


def test_developer_workflow_harness(tmp_path: Path):
    harness = EvaluationHarness(HarnessPolicy(concurrency=2), RunStore(tmp_path / "runs.db"))
    summary = asyncio.run(harness.execute(load_domain("developer_workflow")))
    assert summary.pass_rate == 1.0
    assert any(call.attempt == 2 for result in summary.results for call in result.agent_result.calls)
