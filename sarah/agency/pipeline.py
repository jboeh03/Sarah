"""AgencyPipeline — coordinates the four agents end to end and enforces guardrails.

    Prospector -> Auditor -> SiteBuilder -> OutreachWriter

Spend discipline:
- Paid data sources are gated inside the Prospector (held for approval).
- Demo sites are generated locally (free) and deployed to Vercel's FREE tier by the
  orchestrating agent; a custom domain would cost money and stays behind the gate.
- Outreach is drafted only; the owner sends.

The pipeline persists every prospect with its stage so re-runs target fresh businesses
and never re-contact someone already reached.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
from dataclasses import dataclass, field

from .prospector import Prospector
from .auditor import Auditor
from .builder import SiteBuilder, SiteArtifact
from .outreach import OutreachWriter, OutreachDraft
from .store import ProspectStore
from .models import Prospect, Niche
from ..guardrails import SpendingGuardrail


@dataclass
class AgencyRunResult:
    date: str
    prospects: list = field(default_factory=list)
    built: list = field(default_factory=list)
    drafts: list = field(default_factory=list)
    deploy_manifest: dict = field(default_factory=dict)
    report_markdown: str = ""
    report_path: str = ""
    activity_log: list = field(default_factory=list)


class AgencyPipeline:
    def __init__(self, config: dict | None = None):
        self.config = config or {}
        agency = self.config.get("agency", {})
        owner = self.config.get("owner", {})
        guard_cfg = self.config.get("guardrails", {})
        feeds_cfg = self.config.get("live_feeds", {})

        self.out_dir = agency.get("output_dir", "out/agency")
        self.max_sites = agency.get("max_sites_per_run", 5)
        self.log: list[str] = []

        self.guardrail = SpendingGuardrail(
            require_approval_for_spending=guard_cfg.get("require_approval_for_spending", True),
            max_auto_spend_usd=guard_cfg.get("max_auto_spend_usd", 0.0),
            ledger_path=guard_cfg.get("approval_ledger_path", os.path.join("out", "approvals.jsonl")),
        )

        live = feeds_cfg.get("enabled", True)
        niches = [Niche(n) for n in agency.get("niches", [])] or None
        self.prospector = Prospector(
            seed_path=agency.get("seed_path", "data/agency_seed.json"),
            area=agency.get("area", {}),
            niches=niches,
            live_enabled=live,
            max_prospects=agency.get("max_prospects", 25),
            data_source=agency.get("data_source", "osm"),
            guardrail=self.guardrail,
        )
        # Only check live websites when the network is actually enabled.
        self.auditor = Auditor(check_websites=live and agency.get("check_websites", False))
        self.builder = SiteBuilder(
            out_dir=self.out_dir,
            owner_name=agency.get("owner_name", ""),
            owner_email=owner.get("email", ""),
        )
        self.outreach = OutreachWriter(
            out_dir=self.out_dir,
            owner_name=agency.get("owner_name", ""),
            owner_email=owner.get("email", ""),
            mailing_address=agency.get("mailing_address", ""),
        )
        self.store = ProspectStore(path=os.path.join(self.out_dir, "prospects.json"))

    def run(self) -> AgencyRunResult:
        today = _dt.date.today()
        self.log.append(f"=== Sarah agency run {today.isoformat()} ===")

        # 1) Prospect.
        prospects = self.prospector.find()
        self.log.extend(self.prospector.log)

        # 2) Audit + rank by opportunity.
        ranked = self.auditor.audit_all(prospects)
        self.log.extend(self.auditor.log)

        # 3) Pick fresh, high-opportunity prospects to act on (skip already contacted).
        fresh = [p for p in ranked if not self.store.already_contacted(p)]
        targets = [p for p in fresh if p.opportunity_score() > 0][: self.max_sites]
        self.log.append(f"Selected {len(targets)} fresh prospects to build for.")

        # 4) Build demo sites.
        built: list[SiteArtifact] = self.builder.build_all(targets)
        self.log.extend(self.builder.log)
        manifest = self.builder.deploy_manifest(built)

        # 5) Draft outreach.
        drafts: list[OutreachDraft] = self.outreach.draft_all(targets)
        self.log.extend(self.outreach.log)

        # 6) Persist all prospects (with updated stages) and save.
        self.store.record_all(ranked)
        self.store.save()

        # 7) Report.
        report = self._build_report(today, ranked, targets, built, drafts, manifest)
        report_path = self._write_report(report, today)

        return AgencyRunResult(
            date=today.isoformat(),
            prospects=ranked,
            built=built,
            drafts=drafts,
            deploy_manifest=manifest,
            report_markdown=report,
            report_path=report_path,
            activity_log=self.log,
        )

    # ---- reporting ---------------------------------------------------------

    def _build_report(self, date, ranked, targets, built, drafts, manifest) -> str:
        pending = self.guardrail.pending_summary()
        lines = [
            f"# Sarah Agency — Local Web Prospects · {date.isoformat()}",
            "",
            f"Found **{len(ranked)}** businesses · built **{len(built)}** demo sites · "
            f"drafted **{len(drafts)}** outreach emails · **{len(pending)}** items need spend approval.",
            "",
            "## Top prospects (ranked by opportunity = need × viability)",
            "",
            "| # | Business | Niche | City | Need | Opp. | Website? | Reviews | Contact |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for i, p in enumerate(ranked[:15], 1):
            a = p.audit
            need = f"{a.need_score:.0f}" if a else "—"
            opp = f"{p.opportunity_score():.0f}"
            site = "yes" if p.has_real_website else ("social" if p.social else "none")
            reviews = f"{p.rating}★/{p.review_count}" if p.rating else "none"
            contact = p.phone or p.email or "lookup"
            lines.append(
                f"| {i} | {p.name} | {p.niche.value} | {p.locality} | {need} | {opp} | "
                f"{site} | {reviews} | {contact} |"
            )
        lines += ["", "## Built this run (review, then deploy + send)", ""]
        draft_by_id = {d.prospect_id: d for d in drafts}
        for a in built:
            d = draft_by_id.get(a.prospect_id)
            lookup = " · ⚠️ needs email lookup" if (d and d.needs_contact_lookup) else ""
            lines.append(f"- **{a.business_name}** — demo: `{a.path}` · draft: `{d.path if d else '—'}`{lookup}")
        if not built:
            lines.append("_No fresh prospects to build for this run._")

        lines += ["", "## Deploy (Vercel free tier — no cost)", ""]
        lines.append(
            "Demo sites are static HTML in the paths above. Publish them to Vercel's free "
            "tier for shareable preview links (done via the Vercel MCP tool). A custom "
            "domain would cost money and is held for your approval."
        )

        if pending:
            lines += ["", "## ⚠️ Needs your approval (costs money)", ""]
            for item in pending:
                lines.append(f"- {item['action_name']} — {item['reason']}")

        lines += [
            "", "## Your next steps", "",
            "1. Open the demo sites above in a browser and skim them.",
            "2. Deploy the good ones to Vercel for live preview links (free).",
            "3. Review the Gmail drafts, drop in the live link, and hit send.",
            "4. For any ⚠️ email-lookup rows, find the business email (site/Maps/FB) first.",
            "",
            "_Demo sites use only public business info and are clearly marked proposals. "
            "Outreach drafts are CAN-SPAM-formatted; you are the sender. Nothing was sent "
            "or deployed automatically; nothing cost money._",
        ]
        return "\n".join(lines)

    def _write_report(self, report: str, date) -> str:
        os.makedirs(self.out_dir, exist_ok=True)
        path = os.path.join(self.out_dir, f"report-{date.isoformat()}.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(report)
        latest = os.path.join(self.out_dir, "report-latest.md")
        with open(latest, "w", encoding="utf-8") as fh:
            fh.write(report)
        return path
