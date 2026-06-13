"""Core data model for income opportunities, plus honest expected-value scoring.

Scoring philosophy: rank by *estimated dollars per hour of human effort*, then adjust
for legitimacy, skill fit, and automation risk. We would rather under-promise: pay
ranges are estimates used only for ordering, never guarantees.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass, field, asdict
from typing import Optional


class Category(str, enum.Enum):
    BUG_BOUNTY = "bug_bounty"
    EXPERT_NETWORK = "expert_network"
    PAID_RESEARCH = "paid_research"
    FREELANCE = "freelance"
    OPEN_SOURCE_BOUNTY = "open_source_bounty"
    CONTENT_AFFILIATE = "content_affiliate"
    MICROTASK = "microtask"
    GPT_ADS_SURVEYS = "gpt_ads_surveys"  # tracked only to warn against


class SkillLevel(str, enum.Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Legitimacy(str, enum.Enum):
    UNVETTED = "unvetted"
    REPUTABLE = "reputable"      # well-known, established platform
    PLAUSIBLE = "plausible"      # looks fine but unverified
    SUSPICIOUS = "suspicious"    # red flags present
    SCAM = "scam"               # rejected outright


class AutomationRisk(str, enum.Enum):
    """How risky it is to let a bot do this instead of a human."""
    SAFE = "safe"           # research/aggregation only, no ToS issue
    LOW = "low"
    HIGH = "high"           # ToS prohibits automation; ban/fraud risk
    UNVETTED = "unvetted"


# Skill level -> a rough multiplier on how much the owner's matching skills help.
_SKILL_WEIGHT = {
    SkillLevel.NONE: 1.0,
    SkillLevel.LOW: 1.05,
    SkillLevel.MEDIUM: 1.15,
    SkillLevel.HIGH: 1.25,
}

_LEGIT_WEIGHT = {
    Legitimacy.REPUTABLE: 1.0,
    Legitimacy.PLAUSIBLE: 0.7,
    Legitimacy.UNVETTED: 0.5,
    Legitimacy.SUSPICIOUS: 0.1,
    Legitimacy.SCAM: 0.0,
}

_AUTOMATION_PENALTY = {
    AutomationRisk.SAFE: 1.0,
    AutomationRisk.LOW: 0.95,
    AutomationRisk.UNVETTED: 0.8,
    AutomationRisk.HIGH: 0.25,  # heavily penalize ban-risk categories
}


@dataclass
class Opportunity:
    id: str
    title: str
    category: Category
    source: str
    url: str
    description: str = ""

    # Economics (estimates, per single unit of work: per task / study / bug / hour).
    pay_model: str = "per_task"          # per_task | per_hour | per_study | per_bug | bounty | revenue_share
    est_pay_usd_low: float = 0.0
    est_pay_usd_high: float = 0.0
    est_time_minutes: int = 60

    # Constraints / classification.
    requires_payment_to_start: bool = False   # -> routes to spending guardrail
    requires_human: bool = True               # can the *earning* step be automated?
    skill_level: SkillLevel = SkillLevel.MEDIUM

    # Filled in by the vetter.
    legitimacy: Legitimacy = Legitimacy.UNVETTED
    automation_risk: AutomationRisk = AutomationRisk.UNVETTED
    vetter_notes: list = field(default_factory=list)
    tags: list = field(default_factory=list)

    # ---- derived economics -------------------------------------------------

    # Pay models whose payoff is heavily right-skewed: most attempts yield little or
    # nothing, a rare few pay big. For these, the arithmetic mean wildly overstates a
    # realistic outcome, so we use the geometric mean as an honest central estimate.
    _SKEWED_MODELS = {"per_bug", "bounty"}

    @property
    def est_pay_mid(self) -> float:
        """Honest central estimate of pay per unit of work."""
        lo, hi = self.est_pay_usd_low, self.est_pay_usd_high
        if self.pay_model in self._SKEWED_MODELS and lo > 0 and hi > 0:
            return math.sqrt(lo * hi)  # geometric mean for right-skewed payoffs
        return (lo + hi) / 2.0

    @property
    def est_hourly_usd(self) -> float:
        """Honest estimated dollars per hour of human effort.

        For skewed-payoff work (bounties), this is a *best-case-if-you-succeed* rate;
        it does not discount for the sessions that find nothing, which are common.
        """
        minutes = max(self.est_time_minutes, 1)
        if self.pay_model == "per_hour":
            return self.est_pay_mid
        return self.est_pay_mid * (60.0 / minutes)

    def priority_score(self, owner_skills: Optional[set] = None) -> float:
        """Composite ranking score. Higher = pursue sooner.

        Built from estimated $/hr, dampened by a log so a single huge bounty does not
        dominate, then weighted by legitimacy, automation risk, and skill fit.
        """
        if self.legitimacy == Legitimacy.SCAM:
            return 0.0

        hourly = max(self.est_hourly_usd, 0.0)
        base = math.log10(hourly + 1.0) * 100.0  # 0 at $0/hr, ~200 at ~$100/hr

        score = base
        score *= _LEGIT_WEIGHT.get(self.legitimacy, 0.5)
        score *= _AUTOMATION_PENALTY.get(self.automation_risk, 0.8)
        score *= _SKILL_WEIGHT.get(self.skill_level, 1.0)

        # Reward fit with the owner's actual skills.
        if owner_skills and self.tags:
            if owner_skills & {t.lower() for t in self.tags}:
                score *= 1.2

        # Anything requiring upfront payment is deprioritized (still surfaced for
        # approval, just not auto-promoted to the top).
        if self.requires_payment_to_start:
            score *= 0.6

        return round(score, 2)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["category"] = self.category.value
        d["skill_level"] = self.skill_level.value
        d["legitimacy"] = self.legitimacy.value
        d["automation_risk"] = self.automation_risk.value
        d["est_hourly_usd"] = round(self.est_hourly_usd, 2)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Opportunity":
        d = dict(d)
        d.pop("est_hourly_usd", None)  # derived, not stored
        d["category"] = Category(d["category"])
        d["skill_level"] = SkillLevel(d.get("skill_level", "medium"))
        d["legitimacy"] = Legitimacy(d.get("legitimacy", "unvetted"))
        d["automation_risk"] = AutomationRisk(d.get("automation_risk", "unvetted"))
        known = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in d.items() if k in known})
