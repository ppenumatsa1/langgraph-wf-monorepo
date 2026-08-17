from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from app.modules.order_resolution.hitl import classify_issue
from app.modules.order_resolution.policies import get_policy_for_issue


@dataclass(frozen=True)
class OrderStatus:
    order_id: str
    state: str
    total_amount: float

    def to_dict(self) -> dict[str, str | float]:
        return asdict(self)


def fetch_order_status(order_id: str) -> OrderStatus:
    if order_id.endswith("9"):
        return OrderStatus(order_id=order_id, state="delayed", total_amount=185.0)
    return OrderStatus(order_id=order_id, state="in_transit", total_amount=79.0)


def fetch_policy(issue_type: str) -> str:
    return get_policy_for_issue(issue_type)


def deterministic_inputs(message: str) -> tuple[str, OrderStatus, str]:
    normalized = message.lower()
    order_match = re.search(r"\bord[\s_-]?(\d{4,})\b", normalized)
    order_id = f"ord-{order_match.group(1)}" if order_match else "ord-1001"
    issue_type = classify_issue(normalized)
    order = fetch_order_status(order_id)
    return issue_type, order, fetch_policy(issue_type)


def deterministic_triage_summary(message: str) -> str:
    issue_type, order, _ = deterministic_inputs(message)
    return f"order_id={order.order_id}; issue_type={issue_type}"


def submit_resolution(action: str, order_id: str) -> str:
    return f"resolution_submitted::{action}::{order_id}"
