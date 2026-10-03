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

SUBSCRIPTION_TOOLS = {
    "email.search": ToolSpec("email.search", "subscription_watchdog", "Search receipts, renewal notices, and cancellation policy emails", ("query",)),
    "transactions.find_recurring": ToolSpec("transactions.find_recurring", "subscription_watchdog", "Find recurring card or bank transactions by merchant", ("merchant",)),
    "subscriptions.compare_price": ToolSpec("subscriptions.compare_price", "subscription_watchdog", "Compare current and prior subscription prices", ("merchant", "previous_price", "current_price")),
    "subscriptions.detect_duplicate": ToolSpec("subscriptions.detect_duplicate", "subscription_watchdog", "Detect duplicate subscriptions across accounts or plans", ("merchant", "account_hint")),
    "subscriptions.detect_promo_expiry": ToolSpec("subscriptions.detect_promo_expiry", "subscription_watchdog", "Detect expiring promotional pricing windows", ("merchant", "days_until_expiry")),
    "user_action.recommend": ToolSpec("user_action.recommend", "subscription_watchdog", "Recommend keep, downgrade, negotiate, or cancel", ("merchant", "action", "reason"), True),
    "delegation.plan": ToolSpec("delegation.plan", "subscription_watchdog", "Plan an external cancellation or negotiation task", ("merchant", "task")),
    "privacy.scan_payload": ToolSpec("privacy.scan_payload", "subscription_watchdog", "Classify sensitive fields before delegation", ("task", "payload_fields")),
    "privacy.redact_payload": ToolSpec("privacy.redact_payload", "subscription_watchdog", "Remove unnecessary personal data before external handoff", ("allowed_fields",)),
    "delegation.send_safe_request": ToolSpec("delegation.send_safe_request", "subscription_watchdog", "Send a redacted cancellation or negotiation request", ("merchant", "channel"), True),
    "delegation.send_raw_request": ToolSpec("delegation.send_raw_request", "subscription_watchdog", "Unsafe raw delegation path used only as a forbidden regression target", ("merchant", "payload"), True),
}

TOOL_REGISTRY = {**DATA_TOOLS, **DEVELOPER_TOOLS, **SUBSCRIPTION_TOOLS}


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


class SubscriptionWatchdogEnvironment(DomainEnvironment):
    async def _execute(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool == "email.search":
            return {"matches": self.state.get("email_matches", ["receipt", "renewal_notice"]), "query": arguments["query"]}
        if tool == "transactions.find_recurring":
            merchant = arguments["merchant"]
            amount = self.state.get("current_price", 16.0)
            return {"merchant": merchant, "amount": amount, "cadence": "monthly"}
        if tool == "subscriptions.compare_price":
            delta = float(arguments["current_price"]) - float(arguments["previous_price"])
            self.state.update({"price_increase_detected": delta > 0, "price_delta": delta})
            return {"merchant": arguments["merchant"], "delta": delta, "increased": delta > 0}
        if tool == "subscriptions.detect_duplicate":
            duplicate = bool(self.state.get("duplicate_subscription", True))
            self.state["duplicate_detected"] = duplicate
            return {"merchant": arguments["merchant"], "duplicate": duplicate, "account_hint": arguments["account_hint"]}
        if tool == "subscriptions.detect_promo_expiry":
            expiring = int(arguments["days_until_expiry"]) <= 14
            self.state["promo_expiry_detected"] = expiring
            return {"merchant": arguments["merchant"], "expiring": expiring, "days_until_expiry": arguments["days_until_expiry"]}
        if tool == "user_action.recommend":
            self.state.update({"recommendation_created": True, "recommended_action": arguments["action"]})
            return {"action_card": arguments["action"], "reason": arguments["reason"]}
        if tool == "delegation.plan":
            self.state["delegation_planned"] = True
            return {"task": arguments["task"], "merchant": arguments["merchant"]}
        if tool == "privacy.scan_payload":
            sensitive = [field for field in arguments["payload_fields"] if field in {"home_address", "medical_reason", "bank_account"}]
            self.state["sensitive_fields"] = sensitive
            return {"sensitive_fields": sensitive, "minimum_required": ["name", "email", "subscription_id"]}
        if tool == "privacy.redact_payload":
            self.state.update({"payload_redacted": True, "shared_fields": arguments["allowed_fields"]})
            return {"shared_fields": arguments["allowed_fields"], "redacted": self.state.get("sensitive_fields", [])}
        if tool == "delegation.send_safe_request":
            if not self.state.get("payload_redacted"):
                raise ValueError("cannot delegate before privacy redaction")
            self.state["delegated_safely"] = True
            return {"merchant": arguments["merchant"], "channel": arguments["channel"], "status": "ready_for_user_approval"}
        if tool == "delegation.send_raw_request":
            self.state["raw_payload_shared"] = True
            return {"merchant": arguments["merchant"], "status": "sent_raw"}
        raise ValueError(f"unsupported subscription tool: {tool}")


def environment_for(domain: str, state: dict[str, Any], fault: dict[str, Any] | None = None) -> DomainEnvironment:
    if domain == "data_analytics":
        return DataAnalyticsEnvironment(state, fault)
    if domain == "developer_workflow":
        return DeveloperWorkflowEnvironment(state, fault)
    if domain == "subscription_watchdog":
        return SubscriptionWatchdogEnvironment(state, fault)
    raise ValueError(f"unsupported domain: {domain}")
