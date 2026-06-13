#!/usr/bin/env python3
"""Entrypoint: run one full daily cycle of the Sarah agent team.

    python3 scripts/run_daily.py [--config config/settings.json] [--no-live]

Writes the digest to the configured output directory (default ./out) and prints a short
summary. Nothing that costs money is ever executed — spend-required items are held for
your approval and listed in the digest.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Make the package importable when run as a script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sarah.agents import Orchestrator
from sarah.delivery import build_email_payload


def load_config(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    print(f"[warn] config not found at {path}; using defaults", file=sys.stderr)
    return {}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the Sarah daily opportunity cycle.")
    parser.add_argument("--config", default="config/settings.json")
    parser.add_argument("--no-live", action="store_true", help="skip live feeds (offline)")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    if args.no_live:
        config.setdefault("live_feeds", {})["enabled"] = False

    orchestrator = Orchestrator(config=config)
    result = orchestrator.run()

    # Prepare (but do not send) the email payload.
    owner_email = config.get("owner", {}).get("email", "")
    delivery = config.get("delivery", {})
    if owner_email:
        payload = build_email_payload(result.digest_markdown, to=owner_email)
        payload_path = os.path.join(orchestrator.out_dir, "digest-email.json")
        with open(payload_path, "w", encoding="utf-8") as fh:
            json.dump(payload.to_dict(), fh, indent=2)

    # Console summary.
    print("\n".join(result.activity_log))
    print("-" * 60)
    print(f"Digest written to: {result.digest_path}")
    print(f"Opportunities ranked: {len(result.ranked)}")
    print(f"New since last run:   {len(result.new_ids)}")
    print(f"Held for your spend approval: {len(result.approval_needed)}")
    if delivery.get("send_email"):
        print("\n[delivery] send_email=true — hand digest-email.json to the Gmail MCP tool to send.")
    else:
        print("\n[delivery] send_email=false — nothing emailed. Set it true in config to opt in.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
