from __future__ import annotations

from .models import AgentResult, CaseResult, Scenario, Scores


def _f1(expected: list[str], actual: list[str]) -> float:
    expected_set, actual_set = set(expected), set(actual)
    if not expected_set and not actual_set:
        return 1.0
    precision = len(expected_set & actual_set) / len(actual_set) if actual_set else 0
    recall = len(expected_set & actual_set) / len(expected_set) if expected_set else 0
    return 2 * precision * recall / (precision + recall) if precision + recall else 0


def evaluate(scenario: Scenario, result: AgentResult) -> CaseResult:
    expected_tools = [c.tool for c in scenario.expected_calls]
    actual_tools = [c.tool for c in result.calls if c.success]
    selection = _f1(expected_tools, actual_tools)

    expected_by_tool = {c.tool: c.arguments for c in scenario.expected_calls}
    argument_checks = []
    for call in result.calls:
        if call.success and call.tool in expected_by_tool:
            expected = expected_by_tool[call.tool]
            argument_checks.append(sum(call.arguments.get(k) == v for k, v in expected.items()) / max(len(expected), 1))
    argument_accuracy = sum(argument_checks) / len(argument_checks) if argument_checks else 0

    filtered_actual = [t for t in actual_tools if t in expected_tools]
    sequence = float(filtered_actual == expected_tools)
    state_checks = [result.final_state.get(k) == v for k, v in scenario.expected_state.items()]
    completion = sum(state_checks) / len(state_checks) if state_checks else 1.0
    efficiency = min(1.0, len(expected_tools) / max(len(result.calls), 1))
    overall = 0.2 * selection + 0.2 * argument_accuracy + 0.15 * sequence + 0.35 * completion + 0.1 * efficiency

    failures: list[str] = []
    forbidden = set(actual_tools) & set(scenario.forbidden_tools)
    if forbidden:
        failures.append(f"forbidden tools called: {sorted(forbidden)}")
    if selection < 1:
        failures.append("tool selection mismatch")
    if argument_accuracy < 1:
        failures.append("argument mismatch")
    if sequence < 1:
        failures.append("tool sequence mismatch")
    if completion < 1:
        failures.append("expected final state not reached")

    status = "critical_failure" if forbidden else ("passed" if overall >= 0.85 and completion == 1 else "failed")
    return CaseResult(
        scenario_id=scenario.id,
        scenario_name=scenario.name,
        status=status,
        scores=Scores(
            tool_selection=round(selection, 4), argument_accuracy=round(argument_accuracy, 4),
            sequence=sequence, task_completion=round(completion, 4), efficiency=round(efficiency, 4),
            overall=round(overall, 4),
        ),
        agent_result=result,
        failures=failures,
    )

