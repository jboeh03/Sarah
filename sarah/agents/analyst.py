"""Analyst agent — turns raw candidates into a vetted, ranked shortlist.

It runs each opportunity through the Vetter (scam / ToS / automation classification),
drops outright scams, scores the rest by honest expected value, and sorts them.
"""

from __future__ import annotations

from typing import Optional

from ..models import Opportunity, Legitimacy
from ..vetter import Vetter


class Analyst:
    def __init__(self, owner_skills: Optional[list] = None):
        self.vetter = Vetter()
        self.owner_skills = {s.lower() for s in (owner_skills or [])}
        self.log: list[str] = []

    def analyze(self, opps: list[Opportunity]) -> list[Opportunity]:
        vetted = self.vetter.vet_all(opps)

        kept, rejected = [], []
        for o in vetted:
            if o.legitimacy == Legitimacy.SCAM:
                rejected.append(o)
            else:
                kept.append(o)

        if rejected:
            self.log.append(f"Rejected {len(rejected)} opportunities as scams/red-flagged.")

        kept.sort(key=lambda o: o.priority_score(self.owner_skills), reverse=True)
        self.log.append(f"Vetted and ranked {len(kept)} legitimate opportunities.")
        return kept
