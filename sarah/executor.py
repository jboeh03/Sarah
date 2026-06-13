"""Executor — the action layer. Takes ranked opportunities and, for the ones the
Gatekeeper clears as AUTO, has a worker produce real deliverables. Everything else is
sorted into: held-for-spend-approval, refused-as-ban-risk, or needs-a-human.

This is what turns Sarah from "finds opportunities" into "does the legitimately
automatable work, gated only by spending and account-safety."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import Opportunity
from .gates import Gatekeeper, AUTO, GATE_SPEND, REFUSE_BAN_RISK, HUMAN_REQUIRED
from .workers import ALL_WORKERS, Deliverable, LLMClient


@dataclass
class GatedItem:
    opportunity: Opportunity
    reason: str


@dataclass
class ExecutorResult:
    produced: list = field(default_factory=list)       # list[Deliverable]
    gated_spend: list = field(default_factory=list)    # list[GatedItem]
    refused: list = field(default_factory=list)        # list[GatedItem]
    human_required: list = field(default_factory=list) # list[GatedItem]
    log: list = field(default_factory=list)


class Executor:
    def __init__(
        self,
        gatekeeper: Gatekeeper,
        llm: LLMClient | None = None,
        out_dir: str = "out/work",
        max_auto_per_run: int = 5,
        context: dict | None = None,
    ):
        self.gatekeeper = gatekeeper
        self.context = context or {}
        self.max_auto_per_run = max_auto_per_run
        self.workers = [w(llm=llm, out_dir=out_dir) for w in ALL_WORKERS]

    def run(self, ranked: list[Opportunity]) -> ExecutorResult:
        result = ExecutorResult()
        auto_count = 0

        for opp in ranked:
            decision = self.gatekeeper.evaluate(opp)

            if decision.verdict == REFUSE_BAN_RISK:
                result.refused.append(GatedItem(opp, decision.reason))
            elif decision.verdict == GATE_SPEND:
                result.gated_spend.append(GatedItem(opp, decision.reason))
            elif decision.verdict == HUMAN_REQUIRED:
                result.human_required.append(GatedItem(opp, decision.reason))
            elif decision.verdict == AUTO:
                if auto_count >= self.max_auto_per_run:
                    # Capacity reached this run; treat overflow as queued for a human
                    # to kick next time rather than silently dropping.
                    result.human_required.append(
                        GatedItem(opp, "automatable, but past this run's work budget; queued")
                    )
                    continue
                worker = self._worker_for(opp)
                if worker is None:
                    result.human_required.append(
                        GatedItem(opp, "no worker available for this category yet")
                    )
                    continue
                try:
                    deliverable = worker.produce(opp, context=self.context)
                    result.produced.append(deliverable)
                    auto_count += 1
                    result.log.append(f"Produced: {deliverable.title} -> {deliverable.path}")
                except Exception as exc:  # a single worker failure must not sink the run
                    result.human_required.append(GatedItem(opp, f"auto-production failed: {exc}"))

        result.log.append(
            f"Auto-produced {len(result.produced)} deliverables; "
            f"{len(result.gated_spend)} held for spend approval; "
            f"{len(result.refused)} refused (ban risk); "
            f"{len(result.human_required)} need a human."
        )
        return result

    def _worker_for(self, opp: Opportunity):
        for w in self.workers:
            if w.can_handle(opp.category):
                return w
        return None
