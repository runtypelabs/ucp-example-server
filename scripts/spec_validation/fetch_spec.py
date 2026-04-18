"""Download the UCP spec at tag v2026-04-08 into scripts/spec_validation/spec/.

Pins the validator to a known spec version. Re-run if the tag changes.

Usage:
    uv run python scripts/spec_validation/fetch_spec.py
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

TAG = "v2026-04-08"
REPO = "Universal-Commerce-Protocol/ucp"
API_ROOT = f"https://api.github.com/repos/{REPO}"

SPEC_PATHS = [
    "source/discovery/profile_schema.json",
    "source/schemas/ucp.json",
    "source/schemas/capability.json",
    "source/schemas/payment_handler.json",
    "source/schemas/service.json",
    "source/services/shopping/rest.openapi.json",
    "source/services/shopping/mcp.openrpc.json",
    "source/services/shopping/embedded.openrpc.json",
    "source/schemas/transports/embedded_config.json",
]

SHOPPING_SCHEMAS = [
    "ap2_mandate", "buyer_consent", "cart", "catalog_lookup", "catalog_search",
    "checkout", "discount", "fulfillment", "order", "payment",
]

SHOPPING_TYPES = [
    "account_info", "adjustment", "amount", "available_payment_instrument",
    "binding", "business_fulfillment_config", "buyer", "card_credential",
    "card_payment_instrument", "category", "context", "description",
    "detail_option_value", "error_code", "error_response", "expectation",
    "fulfillment", "fulfillment_available_method", "fulfillment_destination",
    "fulfillment_event", "fulfillment_group", "fulfillment_method",
    "fulfillment_option", "input_correlation", "item", "line_item", "link",
    "media", "merchant_fulfillment_config", "message", "message_error",
    "message_info", "message_warning", "option_value", "order_confirmation",
    "order_line_item", "pagination", "payment_credential", "payment_identity",
    "payment_instrument", "platform_fulfillment_config", "postal_address",
    "price", "price_filter", "price_range", "product", "product_option",
    "rating", "retail_location", "reverse_domain_name", "search_filters",
    "selected_option", "shipping_destination", "signals", "signed_amount",
    "token_credential", "total", "totals", "variant",
]


def build_paths() -> list[str]:
    paths = list(SPEC_PATHS)
    paths += [f"source/schemas/shopping/{name}.json" for name in SHOPPING_SCHEMAS]
    paths += [f"source/schemas/shopping/types/{name}.json" for name in SHOPPING_TYPES]
    return paths


def download(path: str, dest: Path) -> None:
    url = f"https://raw.githubusercontent.com/{REPO}/{TAG}/{path}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=30) as resp:
        dest.write_bytes(resp.read())


def main() -> int:
    out_root = Path(__file__).parent / "spec"
    out_root.mkdir(parents=True, exist_ok=True)

    # Write a stamp file with the tag so the validator can display it.
    (out_root / "VERSION").write_text(TAG + "\n", encoding="utf-8")

    failures: list[str] = []
    for path in build_paths():
        dest = out_root / path
        try:
            download(path, dest)
            print(f"  ok  {path}")
        except Exception as exc:
            failures.append(f"{path}: {exc}")
            print(f"  FAIL {path} -> {exc}", file=sys.stderr)

    if failures:
        print(f"\n{len(failures)} file(s) failed to download", file=sys.stderr)
        return 1
    print(f"\nFetched {len(build_paths())} spec files at tag {TAG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
