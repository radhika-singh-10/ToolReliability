from __future__ import annotations

import asyncio
import copy
import time
from typing import Any


TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "customer.lookup": {"required": ["email"]},
    "order.get": {"required": ["order_id"]},
    "shipping.track": {"required": ["order_id"]},
    "refund.check_eligibility": {"required": ["order_id"]},
    "refund.create": {"required": ["order_id", "reason"]},
    "replacement.create": {"required": ["order_id", "sku"]},
    "inventory.check": {"required": ["sku"]},
    "email.send": {"required": ["to", "subject"]},
}


class ToolEnvironment:
    """Deterministic synthetic commerce backend with fault injection."""

    def __init__(self, initial_state: dict[str, Any], fault: dict[str, Any] | None = None):
        self.state = copy.deepcopy(initial_state)
        self.fault = fault or {}
        self.attempts: dict[str, int] = {}

    async def execute(self, tool: str, arguments: dict[str, Any]) -> tuple[bool, dict[str, Any], str | None, float]:
        started = time.perf_counter()
        self.attempts[tool] = self.attempts.get(tool, 0) + 1
        fault_tool = self.fault.get("tool")
        if fault_tool == tool and self.attempts[tool] == self.fault.get("attempt", 1):
            kind = self.fault.get("type", "timeout")
            if kind == "timeout":
                await asyncio.sleep(0.01)
                return False, {}, "timeout", (time.perf_counter() - started) * 1000
            return False, {}, kind, (time.perf_counter() - started) * 1000

        missing = [key for key in TOOL_SCHEMAS[tool]["required"] if key not in arguments]
        if missing:
            return False, {}, f"missing required arguments: {missing}", (time.perf_counter() - started) * 1000

        response: dict[str, Any] = {"ok": True}
        if tool == "customer.lookup":
            response = {"customer_id": "cust-101", "email": arguments["email"]}
        elif tool == "order.get":
            response = {"order_id": arguments["order_id"], "sku": "SKU-RED-42", "status": "delivered"}
        elif tool == "shipping.track":
            response = {"status": self.state.get("shipping_status", "in_transit")}
        elif tool == "refund.check_eligibility":
            response = {"eligible": self.state.get("refund_eligible", True)}
        elif tool == "refund.create":
            if self.state.get("refund_created"):
                return False, {}, "duplicate refund", (time.perf_counter() - started) * 1000
            self.state["refund_created"] = True
            response = {"refund_id": "ref-9001"}
        elif tool == "inventory.check":
            response = {"available": self.state.get("inventory_available", True)}
        elif tool == "replacement.create":
            self.state["replacement_created"] = True
            response = {"replacement_id": "rep-7001"}
        elif tool == "email.send":
            self.state["email_sent"] = True
            response = {"message_id": "msg-5001"}
        return True, response, None, (time.perf_counter() - started) * 1000

