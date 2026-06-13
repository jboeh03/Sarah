"""Spending guardrail — the one firm rule the owner set.

Nothing that costs money is ever executed automatically. Any action carrying a cost is
routed through ``SpendingGuardrail``, which refuses to authorize it, records it in an
append-only approval ledger, and hands it back for a human decision.

This is intentionally strict and fail-closed: if we are unsure whether an action costs
money, we treat it as if it does.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Optional


class ApprovalRequired(Exception):
    """Raised when an action cannot proceed without explicit human approval."""

    def __init__(self, action: "Action", reason: str):
        self.action = action
        self.reason = reason
        super().__init__(f"Approval required for '{action.name}': {reason}")


@dataclass
class Action:
    """An action an agent wants to take."""
    name: str
    description: str = ""
    costs_money: bool = False
    amount_usd: float = 0.0
    # If the cost is unknown, we must assume it could cost money (fail-closed).
    cost_known: bool = True
    metadata: dict = field(default_factory=dict)

    @property
    def is_free(self) -> bool:
        return self.cost_known and not self.costs_money and self.amount_usd <= 0.0


@dataclass
class ApprovalRequest:
    action_name: str
    description: str
    amount_usd: float
    reason: str
    requested_at: float = field(default_factory=time.time)
    status: str = "pending"  # pending | approved | denied
    metadata: dict = field(default_factory=dict)


class SpendingGuardrail:
    """Authorizes free actions; blocks and logs anything that may cost money."""

    def __init__(
        self,
        require_approval_for_spending: bool = True,
        max_auto_spend_usd: float = 0.0,
        ledger_path: Optional[str] = None,
    ):
        self.require_approval_for_spending = require_approval_for_spending
        self.max_auto_spend_usd = max_auto_spend_usd
        self.ledger_path = ledger_path
        self.pending: list[ApprovalRequest] = []

    # ---- core check --------------------------------------------------------

    def authorize(self, action: Action) -> bool:
        """Return True if the action may proceed automatically.

        Raises ``ApprovalRequired`` (and logs it) if it needs a human decision.
        """
        # Fail-closed: unknown cost is treated as a potential cost.
        potentially_costs = action.costs_money or not action.cost_known

        if not potentially_costs:
            return True

        # There is a (potential) cost. Is it within an explicitly allowed budget?
        if (
            self.require_approval_for_spending is False
            and action.cost_known
            and action.amount_usd <= self.max_auto_spend_usd
        ):
            return True

        reason = self._reason_for(action)
        self._record(action, reason)
        raise ApprovalRequired(action, reason)

    def is_allowed(self, action: Action) -> bool:
        """Non-raising convenience wrapper around :meth:`authorize`."""
        try:
            return self.authorize(action)
        except ApprovalRequired:
            return False

    # ---- helpers -----------------------------------------------------------

    def _reason_for(self, action: Action) -> str:
        if not action.cost_known:
            return "cost is unknown; treated as a potential spend (fail-closed)"
        return (
            f"action would spend ~${action.amount_usd:.2f}, which exceeds the "
            f"autonomous limit of ${self.max_auto_spend_usd:.2f}"
        )

    def _record(self, action: Action, reason: str) -> ApprovalRequest:
        req = ApprovalRequest(
            action_name=action.name,
            description=action.description,
            amount_usd=action.amount_usd,
            reason=reason,
            metadata=action.metadata,
        )
        self.pending.append(req)
        if self.ledger_path:
            os.makedirs(os.path.dirname(self.ledger_path) or ".", exist_ok=True)
            with open(self.ledger_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(asdict(req)) + "\n")
        return req

    def pending_summary(self) -> list[dict]:
        return [asdict(r) for r in self.pending]
