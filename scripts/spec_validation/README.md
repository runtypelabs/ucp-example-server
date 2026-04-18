# UCP spec compliance validators

Scripts that exercise a running UCP server and validate every response against
the **v2026-04-08** JSON schemas from
[Universal-Commerce-Protocol/ucp](https://github.com/Universal-Commerce-Protocol/ucp/releases/tag/v2026-04-08).

The spec release publishes no pre-built validator, so these scripts pin the
schemas locally with `fetch_spec.py` and run JSON Schema Draft 2020-12
validation via `jsonschema` + `referencing` against a real HTTP endpoint.

## Layout

```
scripts/spec_validation/
  spec/                  ← pinned copy of the UCP v2026-04-08 source tree
  fetch_spec.py          ← re-downloads spec/ from the tag
  http_client.py         ← minimal urllib-based UCP client with required headers
  validator.py           ← builds a referencing.Registry over spec/, validate()
  report.py              ← colored PASS/FAIL reporter
  validate_discovery.py  ← GET /.well-known/ucp
  validate_catalog.py    ← POST /catalog/{search,lookup,product}
  validate_cart.py       ← POST/GET/PUT /carts + /carts/{id}/cancel
  validate_checkout.py   ← full checkout → order flow
  run_all.py             ← runs them all and prints a summary
```

## Run

```bash
# Refresh the pinned spec (only needed when the tag updates)
uv run python scripts/spec_validation/fetch_spec.py

# Validate against the default live deployment
uv run --with jsonschema --with referencing \
    python scripts/spec_validation/run_all.py

# Validate against a different server
uv run --with jsonschema --with referencing \
    python scripts/spec_validation/run_all.py http://localhost:8787
```

Exit status is non-zero if any capability has failures, so it drops into CI
cleanly.

## What each validator checks

| Script | Endpoints | Schema anchors |
|---|---|---|
| `validate_discovery.py` | `/.well-known/ucp` | `discovery/profile.json#/$defs/business_profile` |
| `validate_catalog.py` | `/catalog/search`, `/catalog/lookup`, `/catalog/product` | `catalog_search.json`, `catalog_lookup.json` |
| `validate_cart.py` | `/carts`, `/carts/{id}`, `/carts/{id}/cancel` | `shopping/cart.json` |
| `validate_checkout.py` | `/checkout-sessions`, `/checkout-sessions/{id}`, `/checkout-sessions/{id}/complete`, `/orders/{id}` | `shopping/checkout.json`, `shopping/order.json` |

Each validator also asserts a handful of targeted invariants that JSON Schema
cannot express cleanly on its own — e.g. Catalog: variant uses `options`
(not `selected_options`), option values carry `available`/`exists`; Checkout:
`completed` checkout carries `order.{id, permalink_url}`; Order: fulfillment
events use `occurred_at` (not `timestamp`).

## Notes on schema resolution

- `discovery/profile_schema.json` ships with `$id` ending in
  `schemas/discovery/profile.json`, but its internal `$ref`s are relative
  like `../schemas/ucp.json`. Those refs only resolve if the base is
  `.../discovery/profile.json` (no `schemas/` segment), so `validator.py`
  rewrites the `$id` in memory on load. The original `$id` is kept as an
  alias so inbound refs using either form work.
- The top-level `profile_schema.json` uses `oneOf(platform_profile,
  business_profile)`. Both variants are unsealed (`additionalProperties:
  true`), so a real business profile validates under both which makes
  `oneOf` reject it. The spec itself says business profiles are hosted at
  `/.well-known/ucp`, so the validator targets `business_profile` directly.
- The schemas use `ucp_request` annotations to control per-operation
  requiredness. Those annotations are ignored here because every request we
  send is hand-crafted and we validate only *responses*.
