"""Orchestrator — runs one full daily cycle and coordinates the team.

Pipeline:
    Researcher.gather() -> Analyst.analyze() -> split out spend-required items
    -> Reporter.build_digest() -> persist + return result

The orchestrator is where the spending guardrail is enforced for the cycle: every
opportunity that requires upfront payment is routed through ``SpendingGuardrail`` as an
``Action``. Those actions are never auto-executed — they are collected for the human's
approval and surfaced in the digest.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
from dataclasses import dataclass, field

from .researcher import Researcher
from .analyst import Analyst
from .reporter import Reporter
from ..guardrails import SpendingGuardrail, Action, ApprovalRequired
from ..models import Opportunity
from ..store import OpportunityStore


@dataclass
class RunResult:
    date: str
    digest_markdown: str
    ranked: list = field(default_factory=list)
    approval_needed: list = field(default_factory=list)
    new_ids: set = field(default_factory=set)
    activity_log: list = field(default_factory=list)
    digest_path: str | None = None


class Orchestrator:
    def __init__(self, config: dict | None = None):
        self.config = config or {}
        prefs = self.config.get("preferences", {})
        guard_cfg = self.config.get("guardrails", {})
        feeds_cfg = self.config.get("live_feeds", {})
        delivery_cfg = self.config.get("delivery", {})

        self.out_dir = delivery_cfg.get("digest_output_dir", "out")

        self.researcher = Researcher(
            live_feeds_enabled=feeds_cfg.get("enabled", True),
            timeout_seconds=feeds_cfg.get("timeout_seconds", 8),
        )
        self.analyst = Analyst(owner_skills=prefs.get("owner_skills", []))
        self.reporter = Reporter(
            max_items_per_category=prefs.get("max_items_per_category", 8),
            include_not_recommended=prefs.get("include_not_recommended_in_digest", True),
        )
        self.guardrail = SpendingGuardrail(
            require_approval_for_spending=guard_cfg.get("require_approval_for_spending", True),
            max_auto_spend_usd=guard_cfg.get("max_auto_spend_usd", 0.0),
            ledger_path=guard_cfg.get("approval_ledger_path", os.path.join(self.out_dir, "approvals.jsonl")),
        )
        self.store = OpportunityStore(path=os.path.join(self.out_dir, "opportunities.json"))
        self.log: list[str] = []

    def run(self) -> RunResult:
        today = _dt.date.today()
        self.log.append(f"=== Sarah daily run {today.isoformat()} ===")

        # 1) Research.
        candidates = self.researcher.gather()
        self.log.extend(self.researcher.log)

        # 2) Analyze (vet + score).
        ranked = self.analyst.analyze(candidates)
        self.log.extend(self.analyst.log)

        # 3) Enforce the spending guardrail: separate anything that costs money.
        approval_needed = self._isolate_spend_required(ranked)
        actionable = [o for o in ranked if o not in approval_needed]

        # 4) Track what's new since last run.
        new = self.store.record_all(ranked)
        new_ids = {o.id for o in new}
        self.store.save()
        self.log.append(f"{len(new_ids)} new opportunities since last run.")

        # 5) Report.
        digest = self.reporter.build_digest(
            ranked=actionable,
            approval_needed=approval_needed,
            new_ids=new_ids,
            date=today,
        )
        digest_path = self._write_digest(digest, ranked, today)

        return RunResult(
            date=today.isoformat(),
            digest_markdown=digest,
            ranked=ranked,
            approval_needed=approval_needed,
            new_ids=new_ids,
            activity_log=self.log,
            digest_path=digest_path,
        )

    # ---- guardrail enforcement --------------------------------------------

    def _isolate_spend_required(self, ranked: list[Opportunity]) -> list[Opportunity]:
        held: list[Opportunity] = []
        for o in ranked:
            if not o.requires_payment_to_start:
                continue
            action = Action(
                name=f"pursue:{o.id}",
                description=f"Start '{o.title}' on {o.source} (requires upfront payment)",
                costs_money=True,
                cost_known=False,  # unknown amount -> fail closed
                metadata={"opportunity_id": o.id, "url": o.url},
            )
            try:
                self.guardrail.authorize(action)
            except ApprovalRequired as exc:
                self.log.append(f"HELD for approval: {o.title} ({exc.reason})")
                held.append(o)
        return held

    # ---- output ------------------------------------------------------------

    def _write_digest(self, digest: str, ranked: list[Opportunity], date: _dt.date) -> str:
        os.makedirs(self.out_dir, exist_ok=True)
        path = os.path.join(self.out_dir, f"digest-{date.isoformat()}.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(digest)
        # Also write a stable "latest" pointer.
        latest = os.path.join(self.out_dir, "digest-latest.md")
        with open(latest, "w", encoding="utf-8") as fh:
            fh.write(digest)
        # And a machine-readable snapshot of the full ranked set.
        snap = os.path.join(self.out_dir, f"opportunities-{date.isoformat()}.json")
        with open(snap, "w", encoding="utf-8") as fh:
            json.dump(
                {"date": date.isoformat(), "opportunities": [o.to_dict() for o in ranked]},
                fh, indent=2,
            )
        return path
