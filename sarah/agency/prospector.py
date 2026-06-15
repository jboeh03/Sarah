"""Prospector agent — finds local service businesses to pitch.

Default data source is the FREE OpenStreetMap Overpass API (open data, no key). It is
attempted live and degrades gracefully to a bundled seed dataset when the network is
unavailable (mirrors ``sarah/agents/researcher.py``). Paid sources (Google Places,
Yelp) are richer but cost money / need keys, so they are routed through the
``SpendingGuardrail`` and held for owner approval — never used silently.

OpenStreetMap coverage of tiny service businesses is intentionally thin — which is the
whole point: the businesses with no OSM/website footprint are exactly the ones who most
need what we're selling. That's why a paid source is the documented upgrade path.
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional

from .models import Prospect, Niche, make_prospect_id
from ..guardrails import SpendingGuardrail, Action, ApprovalRequired


OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Keywords used both to query OSM by name and to classify a result into a niche.
NICHE_KEYWORDS: dict[Niche, list[str]] = {
    Niche.GRILL_CLEANING: ["grill clean", "bbq clean", "grill restor"],
    Niche.POOL_SERVICE: ["pool service", "pool opening", "pool clean", "pool care"],
    Niche.PRESSURE_WASHING: ["pressure wash", "power wash", "soft wash"],
    Niche.DECK_BUILDING: ["deck build", "deck install", "deck & patio", "decks"],
    Niche.DETAILING: ["auto detail", "car detail", "mobile detail", "detailing"],
    Niche.LANDSCAPING: ["landscap", "lawn care", "lawn service", "lawn & landscape"],
}


def classify_niche(name: str) -> Niche:
    low = (name or "").lower()
    for niche, kws in NICHE_KEYWORDS.items():
        if any(kw in low for kw in kws):
            return niche
    return Niche.OTHER


class Prospector:
    def __init__(
        self,
        seed_path: str = "data/agency_seed.json",
        area: Optional[dict] = None,
        niches: Optional[list] = None,
        live_enabled: bool = True,
        timeout_seconds: int = 10,
        max_prospects: int = 25,
        data_source: str = "osm",
        guardrail: Optional[SpendingGuardrail] = None,
    ):
        self.seed_path = seed_path
        self.area = area or {}
        self.niches = set(niches) if niches else set(NICHE_KEYWORDS.keys())
        self.live_enabled = live_enabled
        self.timeout_seconds = timeout_seconds
        self.max_prospects = max_prospects
        self.data_source = data_source
        self.guardrail = guardrail
        self.log: list[str] = []

    # ---- public API --------------------------------------------------------

    def find(self) -> list[Prospect]:
        prospects: list[Prospect] = []

        if self.data_source in ("google_places", "yelp"):
            # Paid source: must be approved before any call. Routes through the gate.
            self._gate_paid_source()
            # If somehow approved (explicit budget), a real adapter would run here.

        if self.live_enabled and self.data_source == "osm":
            try:
                live = self._fetch_osm()
                prospects.extend(live)
                self.log.append(f"OpenStreetMap returned {len(live)} businesses.")
            except Exception as exc:  # network/parse errors are non-fatal by design
                self.log.append(f"OpenStreetMap unavailable ({exc}); using seed data.")

        # Always fold in seed data; dedupe by id keeps live results authoritative.
        seed = self._load_seed()
        self.log.append(f"Loaded {len(seed)} seed businesses.")

        merged: dict[str, Prospect] = {}
        for p in seed + prospects:  # live last so it overwrites seed on id clash
            merged[p.id] = p

        result = [p for p in merged.values() if p.niche in self.niches or not self.niches]
        result = result[: self.max_prospects]
        self.log.append(f"Prospector surfaced {len(result)} businesses to audit.")
        return result

    # ---- paid-source gate --------------------------------------------------

    def _gate_paid_source(self) -> None:
        action = Action(
            name=f"prospect_via:{self.data_source}",
            description=f"Query {self.data_source} for local businesses (paid API / billing)",
            costs_money=True,
            cost_known=False,  # usage-based; fail closed
            metadata={"data_source": self.data_source},
        )
        guard = self.guardrail or SpendingGuardrail()
        try:
            guard.authorize(action)
        except ApprovalRequired as exc:
            self.log.append(
                f"HELD for approval: {self.data_source} is a paid source ({exc.reason}). "
                f"Falling back to free OpenStreetMap + seed data."
            )
            self.data_source = "osm"

    # ---- OpenStreetMap (free) ---------------------------------------------

    def _fetch_osm(self) -> list[Prospect]:
        import urllib.parse
        import urllib.request

        query = self._build_overpass_query()
        data = urllib.parse.urlencode({"data": query}).encode()
        req = urllib.request.Request(
            OVERPASS_URL, data=data, headers={"User-Agent": "sarah-agency/0.1"}
        )
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
            payload = resp.read().decode("utf-8", errors="replace")
        return self._parse_osm(payload)

    def _build_overpass_query(self) -> str:
        locality = self.area.get("locality", "")
        kw_union = [kw for kws in NICHE_KEYWORDS.values() for kw in kws]
        name_regex = "|".join(re.escape(k) for k in kw_union)
        area_clause = f'area["name"="{locality}"]->.a;' if locality else "area->.a;"
        return (
            "[out:json][timeout:25];"
            f"{area_clause}"
            "("
            f'  nwr(area.a)["name"~"{name_regex}",i];'
            '  nwr(area.a)["shop"="garden_centre"];'
            '  nwr(area.a)["craft"="gardener"];'
            ");"
            "out center tags 60;"
        )

    def _parse_osm(self, payload: str) -> list[Prospect]:
        data = json.loads(payload)
        out: list[Prospect] = []
        for el in data.get("elements", []):
            tags = el.get("tags", {})
            name = tags.get("name")
            if not name:
                continue
            niche = classify_niche(name)
            if niche == Niche.OTHER and tags.get("shop") != "garden_centre" and tags.get("craft") != "gardener":
                continue
            if niche == Niche.OTHER:
                niche = Niche.LANDSCAPING
            locality = tags.get("addr:city", self.area.get("locality", ""))
            out.append(
                Prospect(
                    id=make_prospect_id(name, locality),
                    name=name,
                    niche=niche,
                    locality=locality,
                    region=tags.get("addr:state", self.area.get("region", "")),
                    address=self._osm_address(tags),
                    lat=el.get("lat") or (el.get("center") or {}).get("lat"),
                    lon=el.get("lon") or (el.get("center") or {}).get("lon"),
                    phone=tags.get("phone") or tags.get("contact:phone", ""),
                    email=tags.get("email") or tags.get("contact:email", ""),
                    website=tags.get("website") or tags.get("contact:website", ""),
                    social=tags.get("contact:facebook", ""),
                    on_google_maps=False,  # unknown from OSM
                    source="osm",
                    raw_tags=tags,
                )
            )
        return out

    @staticmethod
    def _osm_address(tags: dict) -> str:
        parts = [
            tags.get("addr:housenumber", ""),
            tags.get("addr:street", ""),
            tags.get("addr:city", ""),
            tags.get("addr:state", ""),
        ]
        return " ".join(p for p in parts if p).strip()

    # ---- seed (offline) ----------------------------------------------------

    def _load_seed(self) -> list[Prospect]:
        if not os.path.exists(self.seed_path):
            return []
        with open(self.seed_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        out = []
        for raw in data.get("businesses", []):
            name = raw.get("name", "")
            locality = raw.get("locality", "")
            out.append(
                Prospect(
                    id=make_prospect_id(name, locality),
                    name=name,
                    niche=Niche(raw.get("niche", "other")),
                    locality=locality,
                    region=raw.get("region", ""),
                    address=raw.get("address", ""),
                    phone=raw.get("phone", ""),
                    email=raw.get("email", ""),
                    website=raw.get("website", ""),
                    social=raw.get("social", ""),
                    rating=raw.get("rating"),
                    review_count=raw.get("review_count"),
                    on_google_maps=raw.get("on_google_maps", False),
                    source=raw.get("source", "seed"),
                )
            )
        return out
