"""Gatekeeper — decides whether an agent may *act* on an opportunity autonomously.

There are exactly two hard gates plus one refusal:

  * SPEND gate     — anything that costs money waits for your approval (your rule).
  * BAN-RISK gate  — anything whose automation would get your account banned or
                     constitutes fraud is REFUSED, not gated. A banned account earns
                     $0, so "protect the account" is part of "make money", not a
                     separate concern.
  * HUMAN-REQUIRED — legitimate work that genuinely needs you (a live call, a verified
                     human test, authorized security testing). Surfaced, not executed.

Everything else is AUTO: the agent does the work without you.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Opportunity, Category, AutomationRisk, Legitimacy
from .guardrails import SpendingGuardrail, Action, ApprovalRequired


# Verdicts.
AUTO = "auto"
GATE_SPEND = "gate_spend"
REFUSE_BAN_RISK = "refuse_ban_risk"
HUMAN_REQUIRED = "human_required"

# Categories whose *production* step an agent can legitimately do end-to-end.
_AUTO_CATEGORIES = {
    Category.OPEN_SOURCE_BOUNTY,
    Category.CONTENT_AFFILIATE,
    Category.FREELANCE,
}


@dataclass
class ExecutionDecision:
    verdict: str
    reason: str

    @property
    def is_auto(self) -> bool:
        return self.verdict == AUTO


class Gatekeeper:
    def __init__(self, spending: SpendingGuardrail):
        self.spending = spending

    def evaluate(self, opp: Opportunity) -> ExecutionDecision:
        # 0) Never act on rejected scams.
        if opp.legitimacy == Legitimacy.SCAM:
            return ExecutionDecision(REFUSE_BAN_RISK, "rejected as a scam by the vetter")

        # 1) Ban-risk / fraud channels are refused outright (not merely gated).
        if opp.automation_risk == AutomationRisk.HIGH:
            return ExecutionDecision(
                REFUSE_BAN_RISK,
                "automating this violates platform ToS (account ban + forfeited "
                "balance) and, for survey/research work, constitutes data fraud",
            )

        # 2) Spend gate — log the request and hold for approval.
        if opp.requires_payment_to_start:
            action = Action(
                name=f"execute:{opp.id}",
                description=f"Act on '{opp.title}' (requires upfront payment)",
                costs_money=True,
                cost_known=False,
                metadata={"opportunity_id": opp.id},
            )
            try:
                self.spending.authorize(action)
            except ApprovalRequired as exc:
                return ExecutionDecision(GATE_SPEND, exc.reason)
            # If somehow authorized (explicit budget), allow.
            return self._auto_or_human(opp)

        # 3) Free + legitimate: auto if we can do the production, else human-required.
        return self._auto_or_human(opp)

    def _auto_or_human(self, opp: Opportunity) -> ExecutionDecision:
        if opp.category in _AUTO_CATEGORIES:
            return ExecutionDecision(AUTO, "production step is fully automatable")
        if opp.category == Category.BUG_BOUNTY:
            return ExecutionDecision(
                HUMAN_REQUIRED,
                "discovery can be assisted, but testing must be human-judged and only "
                "against authorized, in-scope targets",
            )
        return ExecutionDecision(
            HUMAN_REQUIRED,
            "requires a real human (live call / verified human participation)",
        )
