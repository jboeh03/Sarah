"""Local service-business web agency pipeline.

A team of four cooperating agents that turns "businesses with weak online presence" into
ready-to-send proposals:

    Prospector -> Auditor -> SiteBuilder -> OutreachWriter

It runs offline against seed data, gates anything that costs money, builds real demo
sites, and drafts (never sends) outreach. See ``pipeline.AgencyPipeline``.
"""

from .pipeline import AgencyPipeline, AgencyRunResult
from .models import Prospect, AuditResult, Niche, OutreachStage

__all__ = [
    "AgencyPipeline",
    "AgencyRunResult",
    "Prospect",
    "AuditResult",
    "Niche",
    "OutreachStage",
]
