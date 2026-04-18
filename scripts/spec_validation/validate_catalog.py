"""Validate catalog endpoints against UCP v2026-04-08.

Exercises:
    POST /catalog/search  → catalog_search.json#/$defs/search_response
    POST /catalog/lookup  → catalog_lookup.json#/$defs/lookup_response
    POST /catalog/product → catalog_lookup.json#/$defs/get_product_response
"""
from __future__ import annotations

import sys

from http_client import UcpClient
from report import Report, header
from validator import load_registry, validate


SEARCH_RESPONSE = (
    "https://ucp.dev/schemas/shopping/catalog_search.json#/$defs/search_response"
)
LOOKUP_RESPONSE = (
    "https://ucp.dev/schemas/shopping/catalog_lookup.json#/$defs/lookup_response"
)
GET_PRODUCT_RESPONSE = (
    "https://ucp.dev/schemas/shopping/catalog_lookup.json#/$defs/get_product_response"
)


def run(base_url: str) -> Report:
    header(f"Catalog — {base_url}")
    report = Report(capability="Catalog")
    client = UcpClient(base_url)
    registry, _ = load_registry()

    # --- search -----------------------------------------------------------
    resp = client.post("/catalog/search", {"query": "roses"})
    report.add_manual(
        "POST /catalog/search returns 2xx",
        resp.ok,
        note=f"status={resp.status}",
    )
    first_product_id: str | None = None
    if resp.ok and isinstance(resp.body, dict):
        errs = validate(resp.body, SEARCH_RESPONSE, registry=registry)
        report.add("search response matches catalog_search.json#/$defs/search_response", errs)

        products = resp.body.get("products") or []
        report.add_manual(
            "search returned ≥1 product",
            bool(products),
            note=f"count={len(products)}",
        )
        if products:
            first_product_id = products[0].get("id")

    # --- lookup -----------------------------------------------------------
    if first_product_id:
        resp = client.post("/catalog/lookup", {"ids": [first_product_id]})
        report.add_manual(
            "POST /catalog/lookup returns 2xx",
            resp.ok,
            note=f"status={resp.status}, id={first_product_id}",
        )
        if resp.ok and isinstance(resp.body, dict):
            errs = validate(resp.body, LOOKUP_RESPONSE, registry=registry)
            report.add(
                "lookup response matches catalog_lookup.json#/$defs/lookup_response",
                errs,
            )
            # lookup_variant requires "inputs" on each variant
            products = resp.body.get("products") or []
            missing_inputs = [
                (p.get("id"), v.get("id"))
                for p in products
                for v in (p.get("variants") or [])
                if "inputs" not in v
            ]
            report.add_manual(
                "every lookup variant carries 'inputs' (correlation array)",
                not missing_inputs,
                note=f"missing={missing_inputs}" if missing_inputs else None,
            )

    # --- get_product ------------------------------------------------------
    if first_product_id:
        resp = client.post("/catalog/product", {"id": first_product_id})
        report.add_manual(
            "POST /catalog/product returns 2xx",
            resp.ok,
            note=f"status={resp.status}",
        )
        if resp.ok and isinstance(resp.body, dict):
            errs = validate(resp.body, GET_PRODUCT_RESPONSE, registry=registry)
            report.add(
                "get_product response matches catalog_lookup.json#/$defs/get_product_response",
                errs,
            )

            product = resp.body.get("product") or {}
            variants = product.get("variants") or []

            # C1: variant.options field (must not be 'selected_options')
            if variants:
                v0 = variants[0]
                report.add_manual(
                    "variant uses 'options' (not 'selected_options')",
                    "options" in v0 and "selected_options" not in v0,
                )
                report.add_manual(
                    "variant has 'description' field (required by variant.json)",
                    "description" in v0,
                    note="Only checked on first variant",
                )

            # C3: option values include availability signals
            options = product.get("options") or []
            if options:
                any_values = options[0].get("values") or []
                missing_signals = [
                    v for v in any_values
                    if "available" not in v or "exists" not in v
                ]
                report.add_manual(
                    "option values include 'available' and 'exists' signals",
                    not missing_signals,
                    note=f"missing={len(missing_signals)}" if missing_signals else None,
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
