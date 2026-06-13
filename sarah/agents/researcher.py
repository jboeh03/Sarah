"""Researcher agent — gathers candidate opportunities.

Two sources:
  1. A curated, verifiable dataset that ships with the project (always available).
  2. Optional live feeds (RSS/JSON) attempted at runtime, degrading gracefully to the
     curated set when the network is unavailable or blocked.

It does not judge opportunities — that's the Analyst's job. It just casts a wide net.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from ..models import Opportunity, Category


# Optional live feeds. These are real, public endpoints; when the sandbox/network blocks
# them we simply skip and rely on the curated dataset. Add your own here.
DEFAULT_LIVE_FEEDS = [
    # WeWorkRemotely programming jobs (RSS) — freelance/contract leads.
    {
        "name": "weworkremotely-programming",
        "url": "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "category": "freelance",
        "kind": "rss",
    },
    # Hacker News "Freelancer? Seeking Freelancer?" style leads via Algolia API.
    {
        "name": "hn-freelance",
        "url": "https://hn.algolia.com/api/v1/search_by_date?tags=comment&query=freelance&hitsPerPage=20",
        "category": "freelance",
        "kind": "hn_algolia",
    },
]


class Researcher:
    def __init__(
        self,
        dataset_path: str = "data/opportunity_sources.json",
        live_feeds_enabled: bool = True,
        live_feeds: Optional[list] = None,
        timeout_seconds: int = 8,
    ):
        self.dataset_path = dataset_path
        self.live_feeds_enabled = live_feeds_enabled
        self.live_feeds = live_feeds if live_feeds is not None else DEFAULT_LIVE_FEEDS
        self.timeout_seconds = timeout_seconds
        self.log: list[str] = []

    # ---- public API --------------------------------------------------------

    def gather(self) -> list[Opportunity]:
        opps = self._load_curated()
        self.log.append(f"Loaded {len(opps)} curated opportunities.")
        if self.live_feeds_enabled:
            live = self._gather_live()
            self.log.append(f"Fetched {len(live)} live opportunities.")
            opps.extend(live)
        return opps

    # ---- curated -----------------------------------------------------------

    def _load_curated(self) -> list[Opportunity]:
        if not os.path.exists(self.dataset_path):
            self.log.append(f"Curated dataset not found at {self.dataset_path}.")
            return []
        with open(self.dataset_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        out = []
        for raw in data.get("opportunities", []):
            try:
                out.append(Opportunity.from_dict(raw))
            except (KeyError, ValueError) as exc:
                self.log.append(f"Skipped malformed curated entry: {exc}")
        return out

    # ---- live --------------------------------------------------------------

    def _gather_live(self) -> list[Opportunity]:
        results: list[Opportunity] = []
        for feed in self.live_feeds:
            try:
                results.extend(self._fetch_feed(feed))
            except Exception as exc:  # network/parse errors are non-fatal by design
                self.log.append(f"Live feed '{feed['name']}' unavailable ({exc}); skipped.")
        return results

    def _fetch_feed(self, feed: dict) -> list[Opportunity]:
        # Imported lazily so the project runs with zero network and zero extra deps.
        import urllib.request

        req = urllib.request.Request(feed["url"], headers={"User-Agent": "sarah-bot/0.1"})
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
            payload = resp.read().decode("utf-8", errors="replace")

        if feed["kind"] == "hn_algolia":
            return self._parse_hn(feed, payload)
        if feed["kind"] == "rss":
            return self._parse_rss(feed, payload)
        return []

    def _parse_hn(self, feed: dict, payload: str) -> list[Opportunity]:
        data = json.loads(payload)
        out = []
        for hit in data.get("hits", [])[:20]:
            text = (hit.get("comment_text") or "")[:280]
            if not text:
                continue
            oid = f"hn-{hit.get('objectID')}"
            out.append(
                Opportunity(
                    id=oid,
                    title=f"HN freelance lead: {text[:60]}...",
                    category=Category(feed["category"]),
                    source="Hacker News",
                    url=f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                    description=text,
                    pay_model="per_hour",
                    est_pay_usd_low=25,
                    est_pay_usd_high=120,
                    est_time_minutes=60,
                    tags=["freelance"],
                )
            )
        return out

    def _parse_rss(self, feed: dict, payload: str) -> list[Opportunity]:
        # Minimal, dependency-free RSS item extraction.
        import re

        items = re.findall(r"<item>(.*?)</item>", payload, re.DOTALL)[:20]
        out = []
        for i, item in enumerate(items):
            title_m = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", item, re.DOTALL)
            link_m = re.search(r"<link>(.*?)</link>", item, re.DOTALL)
            title = (title_m.group(1).strip() if title_m else "Remote role")[:120]
            link = link_m.group(1).strip() if link_m else feed["url"]
            out.append(
                Opportunity(
                    id=f"{feed['name']}-{i}-{abs(hash(title)) % 10**8}",
                    title=title,
                    category=Category(feed["category"]),
                    source="WeWorkRemotely",
                    url=link,
                    description=title,
                    pay_model="per_hour",
                    est_pay_usd_low=30,
                    est_pay_usd_high=120,
                    est_time_minutes=60,
                    tags=["freelance", "remote"],
                )
            )
        return out
