"""Validate GET /.well-known/ucp against the UCP discovery profile schema.

Usage (standalone):
    uv run --with jsonschema --with referencing \
        python scripts/spec_validation/validate_discovery.py [base_url]
"""
from __future__ import annotations

import sys

from http_client import UcpClient
from report import Report, header
from validator import load_registry, validate


PROFILE_SCHEMA = "https://ucp.dev/discovery/profile.json"
# Per profile_schema.json: "Business profiles are hosted at /.well-known/ucp".
# The full profile uses oneOf(platform_profile, business_profile) which is
# ambiguous for responses that fit both (both allow additionalProperties),
# so we also validate against the business_profile branch directly.
BUSINESS_PROFILE_SCHEMA = "https://ucp.dev/discovery/profile.json#/$defs/business_profile"


def run(base_url: str) -> Report:
    header(f"Discovery — {base_url}/.well-known/ucp")
    report = Report(capability="Discovery")
    client = UcpClient(base_url)
    registry, _ = load_registry()

    resp = client.get("/.well-known/ucp")
    report.add_manual(
        "GET /.well-known/ucp returns 2xx",
        resp.ok,
        note=f"status={resp.status}",
    )
    if not resp.ok or resp.body is None:
        return report

    # Business profile shape (spec: "Business profiles are hosted at /.well-known/ucp")
    errors = validate(resp.body, BUSINESS_PROFILE_SCHEMA, registry=registry)
    report.add("Profile matches business_profile in discovery/profile.json", errors)

    # Targeted invariants that the schema itself cannot express cleanly
    ucp = resp.body.get("ucp", {})

    report.add_manual(
        "ucp.version is 2026-04-08",
        ucp.get("version") == "2026-04-08",
        note=f"got {ucp.get('version')!r}",
    )

    services = ucp.get("services", {})
    shopping = services.get("dev.ucp.shopping", [])
    has_rest = any(b.get("transport") == "rest" for b in shopping)
    report.add_manual(
        "services['dev.ucp.shopping'] advertises a REST binding",
        has_rest,
    )

    capabilities = ucp.get("capabilities", {})
    expected_caps = [
        "dev.ucp.shopping.checkout",
        "dev.ucp.shopping.order",
        "dev.ucp.shopping.cart",
        "dev.ucp.shopping.catalog.search",
        "dev.ucp.shopping.catalog.lookup",
    ]
    missing = [c for c in expected_caps if c not in capabilities]
    report.add_manual(
        "Advertises required shopping capabilities",
        not missing,
        note=f"missing={missing}" if missing else None,
    )

    handlers = ucp.get("payment_handlers", {})
    report.add_manual(
        "Advertises at least one payment handler",
        bool(handlers),
        note=f"handlers={list(handlers)}" if handlers else "none found",
    )

    return report


def main(argv: list[str]) -> int:
    base_url = argv[1] if len(argv) > 1 else "https://ucp.runtype.dev"
    report = run(base_url)
    print()
    print(report.summary())
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
