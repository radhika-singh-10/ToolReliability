import asyncio
from toolreliability.agents import ReferenceCommerceAgent, RegressionAgent
from toolreliability.runner import run_suite
from toolreliability.scenarios import load_scenarios


def test_reference_agent_passes_suite():
    result = asyncio.run(run_suite(load_scenarios("scenarios/commerce.yaml"), ReferenceCommerceAgent()))
    assert result.pass_rate == 1.0
    assert result.passed == result.total


def test_regression_agent_is_detected():
    result = asyncio.run(run_suite(load_scenarios("scenarios/commerce.yaml"), RegressionAgent()))
    assert result.pass_rate < 1.0
    failed = [r for r in result.results if r.status != "passed"]
    assert any("tool selection mismatch" in r.failures for r in failed)

