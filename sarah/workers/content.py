"""Content worker — autonomously drafts a complete, genuine article for monetizable
content/affiliate channels (Medium Partner Program, affiliate blogs).

It produces a real Markdown draft. With an LLMClient wired in, the body is fully
written; offline it produces a complete, fill-in-ready structure. It deliberately does
NOT mass-produce spam: one quality draft per run, with disclosure guidance, because
AI-spam gets de-indexed and earns nothing.
"""

from __future__ import annotations

from ..models import Opportunity, Category
from .base import Worker, Deliverable


_TOPIC_BY_SKILL = {
    "security": "A practical walkthrough: finding your first valid bug bounty (legally)",
    "software_engineering": "Shipping your first paid open-source bounty: a start-to-merge guide",
    "writing": "How to vet 'make money online' offers before wasting an hour on them",
}


class ContentWorker(Worker):
    categories = {Category.CONTENT_AFFILIATE}

    def produce(self, opp: Opportunity, context: dict | None = None) -> Deliverable:
        context = context or {}
        skills = context.get("owner_skills", ["writing"])
        topic = next(
            (_TOPIC_BY_SKILL[s] for s in skills if s in _TOPIC_BY_SKILL),
            "A genuinely useful guide in your area of expertise",
        )

        system = (
            "You are a careful writer. Produce an honest, genuinely useful article. "
            "No hype, no fabricated claims. Disclose affiliate links."
        )
        body = self.llm.generate(system, self._outline(topic))

        content = f"""# {topic}

_Draft autonomously prepared for {opp.source} ({opp.title}). Review, finish, and publish._

{body}

---
### Monetization & compliance notes
- **Affiliate disclosure is required** (FTC): state clearly when a link is affiliate.
- Only recommend things you'd genuinely use; trust is the asset that pays.
- Do not mass-publish near-duplicate AI content — search platforms de-index it and you
  earn nothing. One strong, original piece beats fifty thin ones.
"""
        path = self._write(opp, "article-draft.md", content)
        return Deliverable(
            opportunity_id=opp.id,
            title=f"Article draft: {topic}",
            path=path,
            summary=f"Drafted a publishable article for {opp.source}.",
            next_step="Review/finish the draft, add real affiliate links with disclosure, and publish.",
        )

    def _outline(self, topic: str) -> str:
        return f"""## {topic}

## Who this is for
One paragraph naming the exact reader and the problem they have.

## The short answer
2-3 sentences that deliver the payoff up front.

## Step 1 — <first concrete action>
Specifics, with a real example.

## Step 2 — <second concrete action>
Specifics, with a real example.

## Step 3 — <third concrete action>
Specifics, with a real example.

## Common mistakes
Three honest pitfalls and how to avoid them.

## Tools I actually use
List real tools; mark affiliate links with disclosure.

## Conclusion + call to action
Recap and one clear next step for the reader.
"""
