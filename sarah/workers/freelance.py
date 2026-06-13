"""Freelance worker — autonomously drafts a tailored, ready-to-submit proposal for a
freelance/contract lead (Upwork, Contra, HN/WWR posts).

Winning the contract and getting paid is still a human handshake, but the proposal —
the thing that actually wins the gig — is produced for you, with no human input.
"""

from __future__ import annotations

from ..models import Opportunity, Category
from .base import Worker, Deliverable


class FreelanceWorker(Worker):
    categories = {Category.FREELANCE}

    def produce(self, opp: Opportunity, context: dict | None = None) -> Deliverable:
        context = context or {}
        skills = ", ".join(context.get("owner_skills", ["software engineering"]))
        role = opp.title

        system = (
            "You write concise, specific freelance proposals that lead with the client's "
            "outcome, not your resume. No fluff, no generic openers."
        )
        draft = self.llm.generate(system, self._proposal_prompt(role, skills))

        content = f"""# Proposal draft — {role}

- **Lead:** {opp.source} · **Link:** {opp.url}
- **Relevant skills:** {skills}

{draft}

---
### Before sending
- Swap in one concrete, verifiable result from your portfolio.
- Quote a rate consistent with the value, not the hours.
- Send within hours of the post — speed wins freelance leads.
"""
        path = self._write(opp, "proposal-draft.md", content)
        return Deliverable(
            opportunity_id=opp.id,
            title=f"Proposal draft: {role}",
            path=path,
            summary=f"Drafted a tailored proposal for a {opp.source} lead.",
            next_step="Personalize one portfolio result, set your rate, and submit the proposal.",
        )

    def _proposal_prompt(self, role: str, skills: str) -> str:
        return f"""## Opening (1 sentence)
Name the client's desired outcome for "{role}" and that you can deliver it.

## Why me (2-3 bullets)
Specific, relevant experience in {skills}. One measurable result.

## How I'd approach it (3 steps)
A short plan that shows you understood the brief.

## Logistics
Availability, rate basis, and a single clarifying question that shows engagement.

## Close
One line inviting a quick call.
"""
