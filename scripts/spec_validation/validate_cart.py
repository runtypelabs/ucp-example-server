"""Validate cart endpoints against UCP v2026-04-08 cart.json.

Covers the full CRUD lifecycle:
    POST   /carts
    GET    /carts/{id}
    PUT    /carts/{id}
    POST   /carts/{id}/cancel
"""
from __future__ import annotations

import sys

from http_client import UcpClient, new_idempotency_key
from report import Report, header
from validator import load_registry, validate


CART_SCHEMA = "https://ucp.dev/schemas/shopping/cart.json"


def _sample_line_items(product_id: str) -> list[dict]:
    return [
        {
            "item": {"id": product_id, "title": "Sample Roses"},
            "quantity": 2,
        },
    ]


def _discover_product_id(client: UcpClient) -> str:
    """Find a product id via catalog/search; fall back to a known fixture id."""
    resp = client.post("/catalog/search", {"query": "roses"})
    if resp.ok and isinstance(resp.body, dict):
        products = resp.body.get("products") or []
        if products:
            return products[0].get("id") or "bouquet_roses"
    return "bouquet_roses"


def run(base_url: str) -> Report:
    header(f"Cart — {base_url}/carts")
    report = Report(capability="Cart")
    client = UcpClient(base_url)
    registry, _ = load_registry()

    product_id = _discover_product_id(client)

    # --- create -----------------------------------------------------------
    create_body = {
        "line_items": _sample_line_items(product_id),
        "buyer": {"full_name": "Jane Doe", "email": "jane@example.com"},
        "context": {"address_country": "US", "postal_code": "97201"},
        "currency": "USD",
    }
    resp = client.post(
        "/carts", create_body, idempotency_key=new_idempotency_key(),
    )
    report.add_manual(
        "POST /carts returns 2xx",
        resp.ok,
        note=f"status={resp.status}",
    )
    cart_id: str | None = None
    if resp.ok and isinstance(resp.body, dict):
        errs = validate(resp.body, CART_SCHEMA, registry=registry)
        report.add("create-cart response matches cart.json", errs)
        cart_id = resp.body.get("id")

    if not cart_id:
        report.add_manual("skipping GET/PUT/cancel (no cart id)", False)
        return report

    # --- get --------------------------------------------------------------
    resp = client.get(f"/carts/{cart_id}")
    report.add_manual(
        "GET /carts/{id} returns 2xx",
        resp.ok,
        note=f"status={resp.status}",
    )
    if resp.ok and isinstance(resp.body, dict):
        errs = validate(resp.body, CART_SCHEMA, registry=registry)
        report.add("get-cart response matches cart.json", errs)

    # --- put --------------------------------------------------------------
    put_body = {
        "id": cart_id,
        "line_items": _sample_line_items(product_id) + [
            {"item": {"id": product_id, "title": "Extra Roses"}, "quantity": 1},
        ],
    }
    resp = client.put(
        f"/carts/{cart_id}", put_body, idempotency_key=new_idempotency_key(),
    )
    report.add_manual(
        "PUT /carts/{id} returns 2xx",
        resp.ok,
        note=f"status={resp.status}",
    )
    if resp.ok and isinstance(resp.body, dict):
        errs = validate(resp.body, CART_SCHEMA, registry=registry)
        report.add("put-cart response matches cart.json", errs)

    # --- cancel -----------------------------------------------------------
    resp = client.post(
        f"/carts/{cart_id}/cancel", idempotency_key=new_idempotency_key(),
    )
    report.add_manual(
        "POST /carts/{id}/cancel returns 2xx",
        resp.ok,
        note=f"status={resp.status}",
    )
    if resp.ok and isinstance(resp.body, dict):
        errs = validate(resp.body, CART_SCHEMA, registry=registry)
        report.add("cancel-cart response matches cart.json", errs)

    return report


def main(argv: list[str]) -> int:
    base_url = argv[1] if len(argv) > 1 else "https://ucp.runtype.dev"
    report = run(base_url)
    print()
    print(report.summary())
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
