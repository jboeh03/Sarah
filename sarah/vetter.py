"""The vetter: classifies each opportunity for legitimacy, automation risk, and scam
red flags. This is what keeps the team from pointing you at junk or at things that will
get your accounts banned.

It is deliberately conservative. False positives (flagging a real opportunity as
suspicious) cost you a second look; false negatives (missing a scam) cost you money or
your identity. We bias toward the cheaper mistake.
"""

from __future__ import annotations

import re

from .models import Opportunity, Category, Legitimacy, AutomationRisk


# --- scam / red-flag signals -------------------------------------------------
# Phrases that strongly correlate with scams, MLMs, and pay-to-play schemes.
# These are written to fire on "you must send/pay money or recruit", NOT on benign
# mentions (e.g. being *paid in* gift cards is fine; being asked to *buy* them is not).
_SCAM_PATTERNS = [
    r"\bpay(?:ment)? (?:a )?(?:small )?fee\b",
    r"\b(?:registration|processing|activation|membership|admin(?:istration)?) fee\b",
    r"\bguaranteed (?:income|profit|returns?|money|\$)",
    r"\bdouble your (?:money|crypto|investment|income)\b",
    r"\brisk[- ]free profit\b",
    r"\b(?:get rich|make money) (?:fast|quick|overnight)\b",
    r"\bcrypto (?:doubl|multipl)",
    r"\bmlm\b|\bmulti[- ]level marketing\b|\bdownline\b",
    r"\bpre[- ]?pay\b",
    r"\bsend (?:us )?(?:your )?(?:bank details|bank account|ssn|social security)\b",
    # Being asked to *send/buy/load* gift cards (classic scam), not paid in them.
    r"\b(?:send|buy|purchase|load|wire|pay(?: us| me| with))\b[^.\n]{0,25}\bgift cards?\b",
    r"\bwire (?:us|me|money|funds)\b",
]

# Signals that an "earn" activity prohibits automation (ToS) — ban/fraud risk if botted.
_NO_AUTOMATION_PATTERNS = [
    r"\bwatch ads?\b",
    r"\bpaid[- ]to[- ]click\b|\bptc\b",
    r"\bcomplete surveys?\b|\bsurvey panel\b",
    r"\battention check\b",
    r"\bcaptcha\b",
    r"\bone account per (?:person|household)\b",
    r"\bno automation\b|\bno bots?\b|\bautomated (?:access|use) (?:is )?prohibited\b",
]

# Platforms we recognize as reputable (kept lowercase, matched loosely).
_REPUTABLE_SOURCES = {
    "hackerone", "bugcrowd", "intigriti", "google", "google bug hunters",
    "microsoft", "msrc", "apple", "github", "github security lab",
    "algora", "issuehunt", "gitcoin", "replit",
    "prolific", "user interviews", "userinterviews", "respondent", "wynter",
    "usertesting", "utest", "applause", "testbirds",
    "upwork", "toptal", "contra", "braintrust", "pangea",
    "glg", "alphasights", "guidepoint",
    "amazon mechanical turk", "mturk", "clickworker", "appen", "telus international",
    "medium", "youtube", "impact", "shareasale", "partnerstack", "amazon associates",
}

_SCAM_RE = re.compile("|".join(_SCAM_PATTERNS), re.IGNORECASE)
_NOAUTO_RE = re.compile("|".join(_NO_AUTOMATION_PATTERNS), re.IGNORECASE)


class Vetter:
    """Classifies opportunities in place and returns the (possibly rejected) item."""

    def vet(self, opp: Opportunity) -> Opportunity:
        notes: list[str] = []
        text = f"{opp.title} {opp.description} {' '.join(opp.tags)}".lower()

        # 1) Scam / red-flag screen ------------------------------------------
        scam_hits = _SCAM_RE.findall(text)
        if scam_hits:
            opp.legitimacy = Legitimacy.SCAM
            opp.automation_risk = AutomationRisk.HIGH
            notes.append(
                "Rejected: scam/MLM/pay-to-play red flags "
                f"({sorted(set(h.strip() for h in scam_hits if h.strip()))})."
            )
            opp.vetter_notes = notes
            return opp

        # Asking for upfront payment without a clear, reputable reason is a red flag.
        if opp.requires_payment_to_start and not self._source_is_reputable(opp.source):
            opp.legitimacy = Legitimacy.SUSPICIOUS
            notes.append(
                "Requires upfront payment from an unrecognized source — treat as "
                "suspicious; routed to approval and deprioritized."
            )

        # 2) Legitimacy by source -------------------------------------------
        if opp.legitimacy not in (Legitimacy.SUSPICIOUS, Legitimacy.SCAM):
            if self._source_is_reputable(opp.source):
                opp.legitimacy = Legitimacy.REPUTABLE
            else:
                opp.legitimacy = Legitimacy.PLAUSIBLE
                notes.append("Unrecognized source — verify before investing time.")

        # 3) Automation-risk screen -----------------------------------------
        if opp.category == Category.GPT_ADS_SURVEYS or _NOAUTO_RE.search(text):
            opp.automation_risk = AutomationRisk.HIGH
            opp.requires_human = True
            notes.append(
                "NOT RECOMMENDED for automation: platform ToS prohibits bots; "
                "automating this risks an account ban and (for research/survey work) "
                "counts as data fraud. Pennies even when done by hand."
            )
        elif opp.category in (Category.BUG_BOUNTY,):
            # Research/recon can be assisted, but submitting must be human-judged and
            # only against authorized, in-scope targets.
            opp.automation_risk = AutomationRisk.LOW
            opp.requires_human = True
            notes.append(
                "Discovery can be assisted, but only test AUTHORIZED, in-scope targets "
                "and have a human validate every report. Unauthorized scanning is illegal."
            )
        elif opp.category in (Category.CONTENT_AFFILIATE,):
            opp.automation_risk = AutomationRisk.LOW
            notes.append(
                "Partly automatable, but mass AI-spam content gets de-indexed/banned. "
                "Quality and disclosure rules apply."
            )
        elif opp.automation_risk == AutomationRisk.UNVETTED:
            opp.automation_risk = AutomationRisk.SAFE

        opp.vetter_notes = notes
        return opp

    def _source_is_reputable(self, source: str) -> bool:
        s = (source or "").lower()
        return any(rep in s or s in rep for rep in _REPUTABLE_SOURCES)

    # Convenience for batches.
    def vet_all(self, opps: list[Opportunity]) -> list[Opportunity]:
        return [self.vet(o) for o in opps]
