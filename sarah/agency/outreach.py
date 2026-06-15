"""Outreach agent — drafts the "I built you this — want it live?" email.

Every draft is:
- **Personalized** with a specific audit finding (no generic blast).
- **Honest** — it's framed as a demo/proposal, never implies the site is already live.
- **CAN-SPAM compliant** — truthful subject, clear sender identity, a physical mailing
  address, and an explicit opt-out. The owner is always the sender (the Python only
  writes a draft payload; the Gmail draft is created via MCP and the owner hits send),
  which keeps the legal sender = the owner.

No email is ever sent autonomously. Cold SMS is intentionally not supported (TCPA).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

from .models import Prospect, OutreachStage
from ..workers.base import LLMClient, TemplateLLM
from ..delivery.gmail import build_email_payload, EmailPayload


@dataclass
class OutreachDraft:
    prospect_id: str
    business_name: str
    to: str                 # recipient email ("" if not yet found)
    needs_contact_lookup: bool
    payload: EmailPayload
    path: str = ""


class OutreachWriter:
    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        out_dir: str = "out/agency",
        owner_name: str = "",
        owner_email: str = "",
        mailing_address: str = "",
    ):
        self.llm = llm or TemplateLLM()
        self.out_dir = out_dir
        self.owner_name = owner_name or "A local web designer"
        self.owner_email = owner_email
        # CAN-SPAM requires a valid physical postal address in commercial email.
        self.mailing_address = mailing_address or "[YOUR MAILING ADDRESS — required before sending]"
        self.log: list[str] = []

    def draft(self, p: Prospect) -> OutreachDraft:
        finding = self._lead_finding(p)
        demo_ref = p.demo_url or "[demo link — insert after deploy]"

        subject = f"Built {p.name} a new website demo — want to see it?"
        body_md = self._body(p, finding, demo_ref)

        # Optional real-LLM polish (TemplateLLM offline fallback is skipped).
        if not isinstance(self.llm, TemplateLLM):
            polished = self._polish(p, finding, demo_ref)
            if polished:
                body_md = polished

        payload = build_email_payload(body_md, to=(p.email or ""), headline=subject)

        os.makedirs(os.path.join(self.out_dir, "outreach"), exist_ok=True)
        path = os.path.join(self.out_dir, "outreach", f"{p.id}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(
                {**payload.to_dict(), "prospect_id": p.id, "business": p.name,
                 "needs_contact_lookup": not bool(p.email)},
                fh, indent=2,
            )

        if p.outreach_stage in (OutreachStage.BUILT.value, OutreachStage.AUDITED.value, OutreachStage.NEW.value):
            p.outreach_stage = OutreachStage.DRAFTED.value
        self.log.append(f"Drafted outreach for {p.name}" + ("" if p.email else " (email lookup needed)"))

        return OutreachDraft(
            prospect_id=p.id,
            business_name=p.name,
            to=p.email or "",
            needs_contact_lookup=not bool(p.email),
            payload=payload,
            path=path,
        )

    def draft_all(self, prospects: list[Prospect]) -> list[OutreachDraft]:
        return [self.draft(p) for p in prospects]

    # ---- copy --------------------------------------------------------------

    def _lead_finding(self, p: Prospect) -> str:
        """One specific, true observation to open with (from the audit)."""
        if p.audit and p.audit.signals:
            # Prefer the most compelling presence-gap signal.
            for s in p.audit.signals:
                if "No website" in s or "broken" in s or "social page" in s or "mobile" in s:
                    return s.rstrip(".")
        if not p.has_real_website:
            return "I noticed you don't have a website yet"
        return "I had a look at your online presence"

    def _body(self, p: Prospect, finding: str, demo_ref: str) -> str:
        city = p.locality or "your area"
        rep = ""
        if p.rating and (p.review_count or 0) > 0:
            rep = (
                f"\nYou've clearly earned your reputation ({p.rating}★ over "
                f"{p.review_count} reviews) — a site just makes sure people searching in "
                f"{city} actually find it.\n"
            )
        return f"""Hi {p.name} team,

I'm {self.owner_name}, and I help local {city} businesses get a clean, mobile-friendly web presence.

{finding}, so rather than just pitch you, I went ahead and **built you a real demo site** to look at:

{demo_ref}
{rep}
It's mobile-ready, loads fast, and is set up so customers can call or request a quote in one tap. If you like it, I can have it live this week — and I handle the hosting and updates so you don't have to think about it.

If it's not for you, no problem at all — just reply "not interested" and I won't follow up.

Either way, the demo is yours to look at. What do you think?

Best,
{self.owner_name}
{self.owner_email}

---
{self.owner_name} · {self.mailing_address}
You received this one-time note because your business serves the {city} area. Reply "unsubscribe" or "not interested" and I won't contact you again.
"""

    def _polish(self, p: Prospect, finding: str, demo_ref: str) -> str:
        system = (
            "You write short, warm, non-salesy cold outreach emails from a freelance web "
            "designer to a local service business. Keep it honest, specific, and under "
            "180 words. Must keep: a clear opt-out line and the sender's name, email, and "
            "mailing address footer. Never claim the site is already live."
        )
        prompt = (
            f"Business: {p.name} in {p.locality}. Finding: {finding}. Demo link: {demo_ref}. "
            f"Sender: {self.owner_name} <{self.owner_email}>, address {self.mailing_address}. "
            f"Reputation: {p.rating}★/{p.review_count} reviews."
        )
        try:
            out = self.llm.generate(system, prompt).strip()
            # Safety net: only accept the polish if it preserved an opt-out.
            if out and ("not interested" in out.lower() or "unsubscribe" in out.lower()):
                return out
        except Exception:
            pass
        return ""
