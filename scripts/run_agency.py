#!/usr/bin/env python3
"""Entrypoint: run one cycle of the local web-agency pipeline.

    python3 scripts/run_agency.py [--config config/settings.json] [--no-live]

Prospects local service businesses, audits their online presence, builds real demo
sites, and drafts outreach emails — writing everything under out/agency/. Nothing is
sent, deployed, or paid for automatically.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sarah.agency import AgencyPipeline


def load_config(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    print(f"[warn] config not found at {path}; using defaults", file=sys.stderr)
    return {}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the Sarah local web-agency pipeline.")
    parser.add_argument("--config", default="config/settings.json")
    parser.add_argument("--no-live", action="store_true", help="skip live fetch (offline)")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    if args.no_live:
        config.setdefault("live_feeds", {})["enabled"] = False

    pipeline = AgencyPipeline(config=config)
    result = pipeline.run()

    print("\n".join(result.activity_log))
    print("-" * 60)
    print(f"Report:        {result.report_path}")
    print(f"Prospects:     {len(result.prospects)}")
    print(f"Demo sites:    {len(result.built)}  (under {pipeline.out_dir}/sites/)")
    print(f"Outreach drafts:{len(result.drafts)}  (under {pipeline.out_dir}/outreach/)")

    area = config.get("agency", {}).get("area", {})
    if not area.get("locality"):
        print("\n[setup] Set agency.area.locality to your city in config/settings.json "
              "for live prospecting (offline runs use seed data).")
    if not config.get("agency", {}).get("owner_name"):
        print("[setup] Set agency.owner_name and agency.mailing_address before sending "
              "outreach (CAN-SPAM requires a real sender identity + postal address).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
