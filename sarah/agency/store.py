"""Persistence + dedupe for prospects, modeled on ``sarah/store.py``.

Crucially, this remembers the ``outreach_stage`` of each business across runs, so the
pipeline never re-contacts someone it already reached and can grow into a lightweight
CRM (supporting the eventual "roll several businesses under one LLC" vision).
"""

from __future__ import annotations

import json
import os
import time
from typing import Iterable, Optional

from .models import Prospect


class ProspectStore:
    def __init__(self, path: str = "out/agency/prospects.json"):
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

    def is_new(self, p: Prospect) -> bool:
        return p.id not in self._seen

    def known_stage(self, p: Prospect) -> Optional[str]:
        entry = self._seen.get(p.id)
        return entry.get("outreach_stage") if entry else None

    def already_contacted(self, p: Prospect) -> bool:
        stage = self.known_stage(p)
        return stage in {"drafted", "sent", "replied", "won", "lost"}

    def record(self, p: Prospect) -> None:
        entry = p.to_dict()
        entry["last_seen"] = time.time()
        prior = self._seen.get(p.id)
        entry["first_seen"] = prior.get("first_seen", entry["last_seen"]) if prior else entry["last_seen"]
        self._seen[p.id] = entry

    def record_all(self, prospects: Iterable[Prospect]) -> list[Prospect]:
        """Record all; return the subset that was new this run."""
        new = []
        for p in prospects:
            if self.is_new(p):
                new.append(p)
            self.record(p)
        return new

    def __len__(self) -> int:
        return len(self._seen)
