"""Reporter agent — renders the ranked daily digest as Markdown.

It groups opportunities by category, leads with the highest expected-value legitimate
work, separates anything that needs spending approval, and keeps a clearly labeled
"not recommended" section so you know what to avoid and why.
"""

from __future__ import annotations

import datetime as _dt

from ..models import Opportunity, Category, AutomationRisk


_CATEGORY_TITLES = {
    Category.BUG_BOUNTY: "Bug bounties (highest skilled upside)",
    Category.EXPERT_NETWORK: "Expert networks / consulting",
    Category.PAID_RESEARCH: "Paid B2B / UX research",
    Category.FREELANCE: "Freelance & contract",
    Category.OPEN_SOURCE_BOUNTY: "Open-source bounties",
    Category.CONTENT_AFFILIATE: "Content & affiliate (slow ramp)",
    Category.MICROTASK: "Micro-tasks (filler only)",
    Category.GPT_ADS_SURVEYS: "Surveys / ads / GPT sites",
}

_CATEGORY_ORDER = [
    Category.BUG_BOUNTY,
    Category.EXPERT_NETWORK,
    Category.PAID_RESEARCH,
    Category.FREELANCE,
    Category.OPEN_SOURCE_BOUNTY,
    Category.CONTENT_AFFILIATE,
    Category.MICROTASK,
    Category.GPT_ADS_SURVEYS,
]


class Reporter:
    def __init__(self, max_items_per_category: int = 8, include_not_recommended: bool = True):
        self.max_items_per_category = max_items_per_category
        self.include_not_recommended = include_not_recommended

    def build_digest(
        self,
        ranked: list[Opportunity],
        approval_needed: list[Opportunity] | None = None,
        new_ids: set | None = None,
        date: _dt.date | None = None,
        execution=None,
    ) -> str:
        date = date or _dt.date.today()
        new_ids = new_ids or set()
        approval_needed = approval_needed or []

        lines: list[str] = []
        lines.append(f"# Sarah — Daily Income Opportunities · {date.isoformat()}")
        lines.append("")
        lines.append(self._summary_line(ranked, approval_needed, execution))
        lines.append("")

        # What the agents actually did this run (no human input).
        if execution is not None:
            lines.extend(self._work_done_section(execution))

        # Top picks across all legitimate categories.
        top = [o for o in ranked if o.automation_risk != AutomationRisk.HIGH][:10]
        if top:
            lines.append("## Top picks today (ranked by fit · legitimacy · estimated $/hr)")
            lines.append("")
            lines.append("| # | Opportunity | Est. $/hr | Pay | Effort | Source | Skill |")
            lines.append("|---|---|---|---|---|---|---|")
            for i, o in enumerate(top, 1):
                new_tag = " 🆕" if o.id in new_ids else ""
                lines.append(
                    f"| {i} | [{o.title}]({o.url}){new_tag} | "
                    f"${o.est_hourly_usd:,.0f} | {self._pay_str(o)} | "
                    f"{self._effort_str(o)} | {o.source} | {o.skill_level.value} |"
                )
            lines.append("")

        # Spending-approval section — the owner's firm rule.
        if approval_needed:
            lines.append("## ⚠️ Needs your approval (costs money)")
            lines.append("")
            lines.append("These were **not** acted on. They require spending, so they wait for you:")
            lines.append("")
            for o in approval_needed:
                lines.append(f"- **{o.title}** ({o.source}) — {o.description} → {o.url}")
            lines.append("")

        # Per-category detail.
        by_cat: dict[Category, list[Opportunity]] = {}
        for o in ranked:
            by_cat.setdefault(o.category, []).append(o)

        for cat in _CATEGORY_ORDER:
            items = by_cat.get(cat, [])
            if not items:
                continue
            if cat == Category.GPT_ADS_SURVEYS and not self.include_not_recommended:
                continue
            lines.append(f"## {_CATEGORY_TITLES.get(cat, cat.value)}")
            lines.append("")
            if cat == Category.GPT_ADS_SURVEYS:
                lines.append(
                    "> **Not recommended.** Listed only as a warning. Automating these "
                    "violates platform ToS (instant ban + forfeited balance), survey "
                    "automation is data fraud, and pay is pennies even by hand."
                )
                lines.append("")
            if cat == Category.BUG_BOUNTY:
                lines.append(
                    "> Rates shown are **best-case-if-you-find-a-bug**, using a geometric "
                    "mean of the payout range. Most sessions find nothing; income is "
                    "lumpy and skill-gated. Real upside, but not a steady wage."
                )
                lines.append("")
            for o in items[: self.max_items_per_category]:
                lines.append(self._item_block(o, o.id in new_ids))
            lines.append("")

        lines.append("---")
        lines.append(self._footer())
        return "\n".join(lines)

    # ---- helpers -----------------------------------------------------------

    def _summary_line(self, ranked, approval_needed, execution=None) -> str:
        legit = [o for o in ranked if o.automation_risk != AutomationRisk.HIGH]
        best = max((o.est_hourly_usd for o in legit), default=0.0)
        produced = len(execution.produced) if execution is not None else 0
        return (
            f"**{len(legit)}** vetted opportunities · **{produced}** deliverables produced "
            f"autonomously this run · best estimated rate **${best:,.0f}/hr** · "
            f"**{len(approval_needed)}** awaiting your spend approval."
        )

    def _work_done_section(self, execution) -> list[str]:
        out: list[str] = []
        if execution.produced:
            out.append("## ✅ Produced autonomously this run (no human input)")
            out.append("")
            out.append("Real work product the agents made for you — finish and cash in:")
            out.append("")
            for d in execution.produced:
                out.append(f"- **{d.title}** — {d.summary}")
                out.append(f"  - File: `{d.path}`")
                out.append(f"  - Next step (you): {d.next_step}")
            out.append("")

        if execution.refused:
            out.append("## 🚫 Refused — would get your account banned (not a spend issue)")
            out.append("")
            out.append(
                "These were **not** automated on purpose. Automating them is ToS-violating "
                "fraud that bans your accounts and forfeits balances — it loses money, not makes it:"
            )
            out.append("")
            for g in execution.refused[:8]:
                out.append(f"- **{g.opportunity.title}** ({g.opportunity.source}) — {g.reason}")
            out.append("")

        if execution.human_required:
            out.append("## 🧑 Needs you (legit, but can't be faked)")
            out.append("")
            out.append("High-value work that requires a real human — Sarah surfaced and ranked it:")
            out.append("")
            for g in execution.human_required[:10]:
                out.append(f"- **{g.opportunity.title}** ({g.opportunity.source}) — {g.reason}")
            out.append("")
        return out

    def _pay_str(self, o: Opportunity) -> str:
        if o.est_pay_usd_low == o.est_pay_usd_high:
            base = f"${o.est_pay_usd_low:,.0f}"
        else:
            base = f"${o.est_pay_usd_low:,.0f}–${o.est_pay_usd_high:,.0f}"
        return f"{base} / {o.pay_model.replace('_', ' ')}"

    def _effort_str(self, o: Opportunity) -> str:
        m = o.est_time_minutes
        return f"{m} min" if m < 90 else f"{m/60:.1f} hr"

    def _item_block(self, o: Opportunity, is_new: bool) -> str:
        tag = " 🆕" if is_new else ""
        head = f"### {o.title}{tag}"
        bits = [
            head,
            f"- **Source:** {o.source} · **Est. rate:** ${o.est_hourly_usd:,.0f}/hr · "
            f"**Pay:** {self._pay_str(o)} · **Effort:** {self._effort_str(o)}",
            f"- **Legitimacy:** {o.legitimacy.value} · **Automatable:** "
            f"{'no — human required' if o.requires_human else 'partly'} · "
            f"**Skill:** {o.skill_level.value}",
            f"- {o.description}",
            f"- Link: {o.url}",
        ]
        for note in o.vetter_notes:
            bits.append(f"  - _Note: {note}_")
        return "\n".join(bits) + "\n"

    def _footer(self) -> str:
        return (
            "_Pay figures are estimates for ranking, not guarantees. Sarah found and "
            "vetted these; the high-value ones still need you to execute. Nothing here "
            "cost you money — anything that would was held for your approval._"
        )
