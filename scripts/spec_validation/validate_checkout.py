"""Validate checkout + order endpoints against UCP v2026-04-08.

Covers the full lifecycle:
    POST   /checkout-sessions                 -> checkout.json
    GET    /checkout-sessions/{id}            -> checkout.json
    PUT    /checkout-sessions/{id}            -> checkout.json
    POST   /checkout-sessions/{id}/complete   -> order.json (or checkout.json
                                                 if still in-progress)
    GET    /orders/{order_id}                 -> order.json
"""
from __future__ import annotations

import sys

from http_client import UcpClient, new_idempotency_key
from report import Report, header
from validator import load_registry, validate


CHECKOUT_SCHEMA = "https://ucp.dev/schemas/shopping/checkout.json"
ORDER_SCHEMA = "https://ucp.dev/schemas/shopping/order.json"


def _discover_product_id(client: UcpClient) -> str:
    resp = client.post("/catalog/search", {"query": "roses"})
    if resp.ok and isinstance(resp.body, dict):
        products = resp.body.get("products") or []
        if products:
            return products[0].get("id") or "bouquet_roses"
    return "bouquet_roses"


def _create_body(product_id: str) -> dict:
    return {
        "line_items": [
            {
                "item": {"id": product_id, "title": "Sample Roses"},
                "quantity": 1,
            },
        ],
        "buyer": {"full_name": "Jane Doe", "email": "jane@example.com"},
        "currency": "USD",
        "context": {
            "address_country": "US",
            "postal_code": "97201",
        },
        # Request shipping option quotes by sending a destination.
        "fulfillment": {
            "methods": [
                {
                    "type": "shipping",
                    "destinations": [
                        {
                            "address_country": "US",
                            "postal_code": "97201",
                            "address_region": "OR",
                            "address_locality": "Portland",
                            "street_address": "123 Main St",
                        },
                    ],
                },
            ],
        },
    }


def _select_destination_body(checkout: dict) -> dict | None:
    """Select the first destination on each method so the server returns groups."""
    methods = (checkout.get("fulfillment") or {}).get("methods") or []
    if not methods:
        return None
    selected = []
    for method in methods:
        dest_id = (
            method.get("selected_destination_id")
            or ((method.get("destinations") or [{}])[0].get("id"))
        )
        if not dest_id:
            continue
        selected.append({"id": method.get("id"), "selected_destination_id": dest_id})
    if not selected:
        return None
    return {"fulfillment": {"methods": selected}}


def _select_option_body(checkout: dict) -> dict | None:
    """Select the first option on each group (requires groups to already exist).

    The server replaces method state on PUT, so we also re-send
    ``selected_destination_id`` to preserve the destination selection.
    """
    methods = (checkout.get("fulfillment") or {}).get("methods") or []
    selected_methods = []
    any_option = False
    for method in methods:
        groups = method.get("groups") or []
        new_groups = []
        for group in groups:
            opts = group.get("options") or []
            if not opts:
                continue
            any_option = True
            new_groups.append({
                "id": group.get("id"),
                "selected_option_id": opts[0].get("id"),
            })
        if new_groups:
            selected_methods.append({
                "id": method.get("id"),
                "selected_destination_id": method.get("selected_destination_id")
                    or ((method.get("destinations") or [{}])[0].get("id")),
                "groups": new_groups,
            })
    if not any_option:
        return None
    return {"fulfillment": {"methods": selected_methods}}


def _complete_body() -> dict:
    # google_pay / shop_pay handler_ids short-circuit to success in the demo.
    return {
        "payment": {
            "instruments": [
                {
                    "id": "pi_1",
                    "handler_id": "google_pay",
                    "type": "card",
                    "selected": True,
                    "credential": {"token": "tok_demo"},
                },
            ],
        },
        "signals": {"dev.ucp.buyer_ip": "203.0.113.42"},
    }


def run(base_url: str) -> Report:
    header(f"Checkout — {base_url}/checkout-sessions")
    report = Report(capability="Checkout")
    client = UcpClient(base_url)
    registry, _ = load_registry()

    product_id = _discover_product_id(client)

    # --- create -----------------------------------------------------------
    resp = client.post(
        "/checkout-sessions",
        _create_body(product_id),
        idempotency_key=new_idempotency_key(),
    )
    report.add_manual(
        "POST /checkout-sessions returns 2xx",
        resp.ok,
        note=f"status={resp.status}",
    )
    checkout_id: str | None = None
    checkout_obj: dict | None = None
    if resp.ok and isinstance(resp.body, dict):
        errs = validate(resp.body, CHECKOUT_SCHEMA, registry=registry)
        report.add("create-checkout response matches checkout.json", errs)
        checkout_id = resp.body.get("id")
        checkout_obj = resp.body

    if not checkout_id:
        return report

    # --- get --------------------------------------------------------------
    resp = client.get(f"/checkout-sessions/{checkout_id}")
    report.add_manual(
        "GET /checkout-sessions/{id} returns 2xx",
        resp.ok,
        note=f"status={resp.status}",
    )
    if resp.ok and isinstance(resp.body, dict):
        errs = validate(resp.body, CHECKOUT_SCHEMA, registry=registry)
        report.add("get-checkout response matches checkout.json", errs)
        checkout_obj = resp.body

    # --- put (step 1: select destination so the server returns groups) ---
    dest_body = _select_destination_body(checkout_obj or {})
    if dest_body:
        resp = client.put(
            f"/checkout-sessions/{checkout_id}",
            dest_body,
            idempotency_key=new_idempotency_key(),
        )
        report.add_manual(
            "PUT /checkout-sessions/{id} (select destination) returns 2xx",
            resp.ok,
            note=f"status={resp.status}",
        )
        if resp.ok and isinstance(resp.body, dict):
            errs = validate(resp.body, CHECKOUT_SCHEMA, registry=registry)
            report.add("put-checkout (destination) response matches checkout.json", errs)
            checkout_obj = resp.body

    # --- put (step 2: select shipping option) ----------------------------
    opt_body = _select_option_body(checkout_obj or {})
    if opt_body:
        resp = client.put(
            f"/checkout-sessions/{checkout_id}",
            opt_body,
            idempotency_key=new_idempotency_key(),
        )
        report.add_manual(
            "PUT /checkout-sessions/{id} (select option) returns 2xx",
            resp.ok,
            note=f"status={resp.status}",
        )
        if resp.ok and isinstance(resp.body, dict):
            errs = validate(resp.body, CHECKOUT_SCHEMA, registry=registry)
            report.add("put-checkout (option) response matches checkout.json", errs)
            checkout_obj = resp.body

    # --- complete ---------------------------------------------------------
    resp = client.post(
        f"/checkout-sessions/{checkout_id}/complete",
        _complete_body(),
        idempotency_key=new_idempotency_key(),
    )
    report.add_manual(
        "POST /checkout-sessions/{id}/complete returns 2xx",
        resp.ok,
        note=f"status={resp.status}",
    )
    order_id: str | None = None
    if resp.ok and isinstance(resp.body, dict):
        body = resp.body
        # The complete response is the updated checkout; when successful it
        # also carries an embedded `order: {id, permalink_url}` pointer.
        errs = validate(body, CHECKOUT_SCHEMA, registry=registry)
        report.add("complete-checkout response matches checkout.json", errs)

        report.add_manual(
            "completed checkout has status='completed'",
            body.get("status") == "completed",
            note=f"got {body.get('status')!r}",
        )
        report.add_manual(
            "completed checkout carries order.{id,permalink_url}",
            isinstance(body.get("order"), dict) and body["order"].get("id"),
            note=f"order={body.get('order')!r}",
        )
        order_id = (body.get("order") or {}).get("id")

    # --- get order --------------------------------------------------------
    if order_id:
        resp = client.get(f"/orders/{order_id}")
        report.add_manual(
            "GET /orders/{id} returns 2xx",
            resp.ok,
            note=f"status={resp.status}",
        )
        if resp.ok and isinstance(resp.body, dict):
            errs = validate(resp.body, ORDER_SCHEMA, registry=registry)
            report.add("get-order response matches order.json", errs)

            # O3: Order must include currency
            report.add_manual(
                "order.currency is present",
                bool(resp.body.get("currency")),
                note=f"got {resp.body.get('currency')!r}",
            )

            # O4: fulfillment events use occurred_at, not timestamp
            events = (resp.body.get("fulfillment") or {}).get("events") or []
            bad = [
                e for e in events
                if "timestamp" in e or "occurred_at" not in e
            ]
            report.add_manual(
                "fulfillment events use 'occurred_at' (not 'timestamp')",
                not bad,
                note=f"bad_events={len(bad)}" if bad else "no events to check"
                if not events else None,
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
