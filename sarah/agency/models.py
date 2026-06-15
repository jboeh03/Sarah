"""Data models for the local service-business web-agency pipeline.

A ``Prospect`` is a local business the agents found. The pipeline walks it through
stages: found -> audited -> demo built -> outreach drafted -> (human sends) -> won/lost.

The Auditor attaches an ``AuditResult`` whose ``need_score`` is high when the business
has a weak online presence (no/broken site, few reviews, not on maps). The best
prospects combine *high need* (weak web presence) with *high viability* (a real,
reachable, reviewed business) — those are the easiest, most valuable sells.

Mirrors the style of ``sarah/models.py`` (stable ids, to_dict/from_dict, scoring).
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field, asdict
from typing import Optional


class Niche(str, enum.Enum):
    GRILL_CLEANING = "grill_cleaning"
    POOL_SERVICE = "pool_service"
    PRESSURE_WASHING = "pressure_washing"
    DECK_BUILDING = "deck_building"
    DETAILING = "detailing"
    LANDSCAPING = "landscaping"
    OTHER = "other"


class OutreachStage(str, enum.Enum):
    NEW = "new"
    AUDITED = "audited"
    BUILT = "built"
    DRAFTED = "drafted"
    SENT = "sent"          # set by a human after they send
    REPLIED = "replied"
    WON = "won"
    LOST = "lost"


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-") or "x"


def make_prospect_id(name: str, locality: str) -> str:
    """Stable id from business name + locality, so re-runs dedupe cleanly."""
    return f"{slugify(name)}--{slugify(locality)}"


@dataclass
class AuditResult:
    """The Auditor's read on a business's online presence."""
    has_website: bool = False
    website_reachable: Optional[bool] = None     # None = not checked (offline)
    website_https: Optional[bool] = None
    mobile_viewport: Optional[bool] = None       # rough mobile-friendliness signal
    has_reviews: bool = False
    review_count: int = 0
    rating: Optional[float] = None
    on_google_maps: bool = False
    contactable: bool = False                    # has phone or email to reach them
    need_score: float = 0.0                      # 0..100, higher = weaker presence
    signals: list = field(default_factory=list)  # human-readable findings

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "AuditResult":
        known = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in (d or {}).items() if k in known})


@dataclass
class Prospect:
    id: str
    name: str
    niche: Niche = Niche.OTHER

    # Location
    locality: str = ""        # city / town
    region: str = ""          # state / province
    address: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None

    # Contact
    phone: str = ""
    email: str = ""

    # Online-presence signals (as found by the data source)
    website: str = ""
    social: str = ""          # e.g. a Facebook page used in lieu of a website
    rating: Optional[float] = None
    review_count: Optional[int] = None
    on_google_maps: bool = False

    source: str = "seed"      # seed | osm | google_places | yelp
    raw_tags: dict = field(default_factory=dict)

    # Filled by the pipeline
    audit: Optional[AuditResult] = None
    outreach_stage: str = OutreachStage.NEW.value
    demo_site_path: str = ""
    demo_url: str = ""
    notes: list = field(default_factory=list)

    # ---- derived ----------------------------------------------------------

    @property
    def has_real_website(self) -> bool:
        """A social page (Facebook/Instagram) does not count as a real website."""
        w = (self.website or "").lower()
        if not w:
            return False
        return not any(s in w for s in ("facebook.com", "instagram.com", "linktr.ee"))

    @property
    def has_social_presence(self) -> bool:
        """True if they have a social page — in the social field OR a social URL that
        was recorded in the website field instead."""
        if self.social:
            return True
        return bool(self.website) and not self.has_real_website

    def opportunity_score(self) -> float:
        """How attractive this prospect is to pursue. Higher = pursue sooner.

        ``opportunity = need × viability``. Need is weak-web-presence (the gap we fill);
        viability is proof it's a real, active, reputable business (demand we can serve).
        The sweet spot the owner described — a *great* business with a poor online
        presence — needs both, so viability is weighted to reward proven demand and to
        discount businesses showing no signs of activity (no reviews and not on the map).
        """
        if self.audit is None:
            return 0.0
        need = self.audit.need_score  # 0..100

        viability = 1.0
        if self.audit.contactable:
            viability += 0.3
        if self.audit.has_reviews:
            viability += 0.2
        if (self.review_count or 0) >= 10:
            viability += 0.5   # clearly an active business with steady demand
        if (self.rating or 0) >= 4.5:
            viability += 0.3   # strong reputation, just no website to show it off
        elif (self.rating or 0) >= 4.0:
            viability += 0.15

        # Discount businesses with no signs of activity — likely new/inactive, riskier.
        if (self.review_count or 0) == 0 and not self.audit.on_google_maps:
            viability *= 0.5

        return round(need * viability, 2)

    # ---- serialization ----------------------------------------------------

    def to_dict(self) -> dict:
        d = asdict(self)
        d["niche"] = self.niche.value
        d["audit"] = self.audit.to_dict() if self.audit else None
        d["opportunity_score"] = self.opportunity_score()
        d["has_real_website"] = self.has_real_website
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Prospect":
        d = dict(d)
        for derived in ("opportunity_score", "has_real_website"):
            d.pop(derived, None)
        d["niche"] = Niche(d.get("niche", "other"))
        if d.get("audit"):
            d["audit"] = AuditResult.from_dict(d["audit"])
        known = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in d.items() if k in known})
