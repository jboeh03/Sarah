"""The agent team.

Each agent has one job; the orchestrator coordinates them and enforces the spending
guardrail across the whole cycle.

    Researcher  -> gathers candidate opportunities (curated + live feeds)
    Analyst     -> vets (scam/ToS/automation) and scores them honestly
    Reporter    -> renders the ranked daily digest
    Orchestrator-> runs the cycle, dedupes, and isolates anything that costs money
"""

from .researcher import Researcher
from .analyst import Analyst
from .reporter import Reporter
from .orchestrator import Orchestrator, RunResult

__all__ = ["Researcher", "Analyst", "Reporter", "Orchestrator", "RunResult"]
