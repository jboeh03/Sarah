"""Shared worker plumbing: the deliverable type, the LLM seam, and a base class."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from ..models import Opportunity, Category


@dataclass
class Deliverable:
    """A real artifact an agent produced, plus a one-line summary for the digest."""
    opportunity_id: str
    title: str
    path: str
    summary: str
    next_step: str  # what the human does to turn this into money


class LLMClient(Protocol):
    """Provider-agnostic text generation seam.

    Implement ``generate`` with any model to upgrade drafts to full quality. The system
    never depends on a specific provider; offline it uses :class:`TemplateLLM`.
    """

    def generate(self, system: str, prompt: str) -> str: ...


class TemplateLLM:
    """Deterministic, offline fallback. Produces structured scaffolding, not prose.

    Honest by design: it does not pretend to be a finished article — it lays out a
    complete, fill-in-ready structure so a human (or a real LLM) can finish fast.
    """

    def generate(self, system: str, prompt: str) -> str:
        return (
            "<!-- Generated offline by TemplateLLM (structured scaffold). Wire an "
            "LLMClient to produce finished output. -->\n\n" + prompt.strip()
        )


class Worker:
    """Base class. Subclasses set ``categories`` and implement ``produce``."""

    categories: set = set()

    def __init__(self, llm: LLMClient | None = None, out_dir: str = "out/work"):
        self.llm = llm or TemplateLLM()
        self.out_dir = out_dir

    def can_handle(self, category: Category) -> bool:
        return category in self.categories

    def produce(self, opp: Opportunity, context: dict | None = None) -> Deliverable:
        raise NotImplementedError

    # ---- helpers -----------------------------------------------------------

    def _write(self, opp: Opportunity, filename: str, content: str) -> str:
        d = os.path.join(self.out_dir, opp.id)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, filename)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return path
