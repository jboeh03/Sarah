"""Workers — the agents that actually *produce* earning work product autonomously.

Each worker takes an opportunity and emits a real deliverable file (an article draft,
a bounty solution scaffold, a freelance proposal). They are provider-agnostic: plug any
LLM into ``LLMClient`` to upgrade the drafts to full quality; offline they fall back to
structured templates so the system always produces something real.
"""

from .base import Worker, Deliverable, LLMClient, TemplateLLM
from .content import ContentWorker
from .oss_bounty import OSSBountyWorker
from .freelance import FreelanceWorker

ALL_WORKERS = [OSSBountyWorker, ContentWorker, FreelanceWorker]

__all__ = [
    "Worker", "Deliverable", "LLMClient", "TemplateLLM",
    "ContentWorker", "OSSBountyWorker", "FreelanceWorker", "ALL_WORKERS",
]
