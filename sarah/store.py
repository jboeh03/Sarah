"""Lightweight JSON persistence with dedupe, so the team remembers what it has already
seen and can surface only what is new or changed each day.
"""

from __future__ import annotations

import json
import os
import time
from typing import Iterable

from .models import Opportunity


class OpportunityStore:
    def __init__(self, path: str = "out/opportunities.json"):
        self.path = path
        self._seen: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as fh:
                    self._seen = json.load(fh)
            except (json.JSONDecodeError, OSError):
                self._seen = {}

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self._seen, fh, indent=2, sort_keys=True)

    def is_new(self, opp: Opportunity) -> bool:
        return opp.id not in self._seen

    def record(self, opp: Opportunity) -> None:
        entry = opp.to_dict()
        entry["last_seen"] = time.time()
        if opp.id not in self._seen:
            entry["first_seen"] = entry["last_seen"]
        else:
            entry["first_seen"] = self._seen[opp.id].get("first_seen", entry["last_seen"])
        self._seen[opp.id] = entry

    def record_all(self, opps: Iterable[Opportunity]) -> list[Opportunity]:
        """Record all; return the subset that was new this run."""
        new = []
        for o in opps:
            if self.is_new(o):
                new.append(o)
            self.record(o)
        return new

    def __len__(self) -> int:
        return len(self._seen)
