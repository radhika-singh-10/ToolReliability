from __future__ import annotations

import asyncio
import copy
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolSpec:
    name: str
    domain: str
    description: str
    required: tuple[str, ...]
    side_effecting: bool = False


DATA_TOOLS = {
    "catalog.get_schema": ToolSpec("catalog.get_schema", "data_analytics", "Return table and column metadata", ("table",)),
    "warehouse.execute_sql": ToolSpec("warehouse.execute_sql", "data_analytics", "Execute read-only analytical SQL", ("query",)),
    "analytics.validate_result": ToolSpec("analytics.validate_result", "data_analytics", "Validate result shape and business rules", ("result_id",)),
    "charts.create": ToolSpec("charts.create", "data_analytics", "Create a chart from a validated result", ("result_id", "chart_type"), True),
    "exports.create": ToolSpec("exports.create", "data_analytics", "Export validated data", ("result_id", "format"), True),
}

DEVELOPER_TOOLS = {
    "repo.inspect": ToolSpec("repo.inspect", "developer_workflow", "Inspect repository metadata", ("repository",)),
    "repo.search_code": ToolSpec("repo.search_code", "developer_workflow", "Search repository code", ("repository", "query")),
    "issues.search": ToolSpec("issues.search", "developer_workflow", "Find existing issues", ("repository", "query")),
    "issues.create": ToolSpec("issues.create", "developer_workflow", "Create an issue", ("repository", "title"), True),
    "branches.create": ToolSpec("branches.create", "developer_workflow", "Create a branch", ("repository", "branch", "base"), True),
    "ci.get_status": ToolSpec("ci.get_status", "developer_workflow", "Return CI status for a ref", ("repository", "ref")),
}

TOOL_REGISTRY = {**DATA_TOOLS, **DEVELOPER_TOOLS}


class DomainEnvironment(ABC):
    def __init__(self, initial_state: dict[str, Any], fault: dict[str, Any] | None = None):
        self.state = copy.deepcopy(initial_state)
        self.fault = fault or {}
        self.attempts: dict[str, int] = {}

    async def execute(self, tool: str, arguments: dict[str, Any]) -> tuple[bool, dict[str, Any], str | None, float, int]:
        started = time.perf_counter()
        spec = TOOL_REGISTRY.get(tool)
        if not spec:
            return False, {}, "unknown tool", 0, 1
        self.attempts[tool] = self.attempts.get(tool, 0) + 1
        attempt = self.attempts[tool]
        missing = [field for field in spec.required if field not in arguments]
        if missing:
            return False, {}, f"missing required arguments: {missing}", 0, attempt
        if self.fault.get("tool") == tool and attempt == self.fault.get("attempt", 1):
            kind = self.fault.get("type", "timeout")
            if kind == "timeout":
                await asyncio.sleep(0.01)
            return False, {}, kind, (time.perf_counter() - started) * 1000, attempt
        response = await self._execute(tool, arguments)
        return True, response, None, (time.perf_counter() - started) * 1000, attempt

    @abstractmethod
    async def _execute(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]: ...


class DataAnalyticsEnvironment(DomainEnvironment):
    async def _execute(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool == "catalog.get_schema":
            return {"table": arguments["table"], "columns": self.state.get("columns", ["region", "revenue", "created_at"])}
        if tool == "warehouse.execute_sql":
            query = arguments["query"].strip().lower()
            if not query.startswith("select") or any(word in query for word in ("delete ", "update ", "drop ", "insert ")):
                raise ValueError("only read-only SELECT statements are allowed")
            result_id = "result-101"
            self.state.update({"sql_executed": True, "result_id": result_id, "rows": self.state.get("rows", 12)})
            return {"result_id": result_id, "row_count": self.state["rows"]}
        if tool == "analytics.validate_result":
            valid = arguments["result_id"] == self.state.get("result_id")
            self.state["result_validated"] = valid
            return {"valid": valid, "checks": ["non_empty", "expected_columns"]}
        if tool == "charts.create":
            self.state["chart_created"] = True
            return {"chart_id": "chart-101", "type": arguments["chart_type"]}
        if tool == "exports.create":
            self.state["export_created"] = True
            return {"export_id": "export-101", "format": arguments["format"]}
        raise ValueError(f"unsupported data tool: {tool}")


class DeveloperWorkflowEnvironment(DomainEnvironment):
    async def _execute(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool == "repo.inspect":
            return {"repository": arguments["repository"], "default_branch": self.state.get("default_branch", "main")}
        if tool == "repo.search_code":
            return {"matches": self.state.get("matches", ["src/api.py:42"])}
        if tool == "issues.search":
            return {"issues": self.state.get("existing_issues", [])}
        if tool == "issues.create":
            if self.state.get("issue_created"):
                raise ValueError("duplicate issue")
            self.state["issue_created"] = True
            return {"issue_number": 42}
        if tool == "branches.create":
            if self.state.get("branch_created"):
                raise ValueError("duplicate branch")
            self.state["branch_created"] = True
            return {"branch": arguments["branch"]}
        if tool == "ci.get_status":
            self.state["ci_checked"] = True
            return {"status": self.state.get("ci_status", "success")}
        raise ValueError(f"unsupported developer tool: {tool}")


def environment_for(domain: str, state: dict[str, Any], fault: dict[str, Any] | None = None) -> DomainEnvironment:
    if domain == "data_analytics":
        return DataAnalyticsEnvironment(state, fault)
    if domain == "developer_workflow":
        return DeveloperWorkflowEnvironment(state, fault)
    raise ValueError(f"unsupported domain: {domain}")
