"""Orchestrator: run every UCP capability validator and summarize.

Usage:
    uv run --with jsonschema --with referencing \
        python scripts/spec_validation/run_all.py [base_url]

Exits non-zero if any capability has failures.
"""
from __future__ import annotations

import sys

import validate_cart
import validate_catalog
import validate_checkout
import validate_discovery
from report import Report


def main(argv: list[str]) -> int:
    base_url = argv[1] if len(argv) > 1 else "https://ucp.runtype.dev"

    reports: list[Report] = [
        validate_discovery.run(base_url),
        validate_catalog.run(base_url),
        validate_cart.run(base_url),
        validate_checkout.run(base_url),
    ]

    print()
    print("=" * 60)
    print(f"UCP v2026-04-08 compliance summary for {base_url}")
    print("=" * 60)
    any_failed = False
    for r in reports:
        print("  " + r.summary())
        if not r.passed:
            any_failed = True

    # Flat dump of every failure so nothing is hidden in scroll-back
    failures = [
        (r.capability, c)
        for r in reports
        for c in r.checks
        if not c.passed
    ]
    if failures:
        print()
        print(f"{len(failures)} failing check(s):")
        for cap, c in failures:
            note = f" ({c.note})" if c.note else ""
            print(f"  - [{cap}] {c.name}{note}")

    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
