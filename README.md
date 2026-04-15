# UCP Example Store Server

A reference implementation of a UCP Merchant Server running as a **Python Worker
on Cloudflare**, using **FastAPI** and **Cloudflare D1** (serverless SQLite).

Implements the UCP **v2026-04-08** specification including the new Catalog Search
and Catalog Lookup capabilities for product discovery.

**Live demo** (reference deployment): https://ucp.runtype.dev

## Capabilities

| Capability | Endpoints |
|-----------|-----------|
| Catalog Search | `POST /catalog/search` |
| Catalog Lookup | `POST /catalog/lookup`, `POST /catalog/product` |
| Checkout | `POST /checkout-sessions`, `GET/PUT /checkout-sessions/{id}` |
| Checkout Complete | `POST /checkout-sessions/{id}/complete` |
| Discount | Applied via `PUT /checkout-sessions/{id}` |
| Fulfillment | Applied via `PUT /checkout-sessions/{id}` |
| Order | `GET /orders/{id}`, `PUT /orders/{id}` |
| Cart | `POST /carts`, `GET/PUT /carts/{id}`, `POST /carts/{id}/cancel` |
| Discovery | `GET /.well-known/ucp` |

## Prerequisites

1. Install [uv](https://docs.astral.sh/uv/): `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. Install [Node.js](https://nodejs.org/) (for wrangler)
3. A Cloudflare account (free tier works)

## Local Development

```bash
cd ucp-cloudflare-workers

# Install dependencies (includes workers-py, workers-runtime-sdk, pytest)
uv venv && uv sync --all-groups

# Create and seed the local D1 database
npx wrangler d1 execute ucp-flower-shop --local --file=migrations/0001_schema.sql
npx wrangler d1 execute ucp-flower-shop --local --file=migrations/0002_seed.sql
npx wrangler d1 execute ucp-flower-shop --local --file=migrations/0003_catalog.sql
npx wrangler d1 execute ucp-flower-shop --local --file=migrations/0004_carts.sql
npx wrangler d1 execute ucp-flower-shop --local --file=migrations/0005_product_options.sql

# Start the dev server
uv run pywrangler dev --port 8787
```

## Test

```bash
# Discovery
curl http://localhost:8787/.well-known/ucp | python3 -m json.tool

# Search catalog
curl -X POST http://localhost:8787/catalog/search \
  -H "Content-Type: application/json" \
  -H 'UCP-Agent: profile="https://agent.example/profile"' \
  -H "request-signature: test" \
  -H "request-id: test-1" \
  -d '{"query": "roses"}'

# Create checkout
curl -X POST http://localhost:8787/checkout-sessions \
  -H "Content-Type: application/json" \
  -H 'UCP-Agent: profile="https://agent.example/profile"' \
  -H "request-signature: test" \
  -H "idempotency-key: test-key" \
  -H "request-id: test-2" \
  -d '{
    "line_items": [{"item": {"id": "bouquet_roses", "title": "Roses"}, "quantity": 1}],
    "buyer": {"full_name": "Jane Doe", "email": "jane@example.com"},
    "currency": "USD",
    "payment": {"instruments": [], "handlers": []}
  }'
```

## Unit tests

```bash
uv run pytest
```

## Deploy

```bash
# Login to Cloudflare
npx wrangler login

# Set your account ID in wrangler.toml or env
export CLOUDFLARE_ACCOUNT_ID="your-account-id"

# Create the D1 database
npx wrangler d1 create ucp-flower-shop
# Update database_id in wrangler.toml with the returned ID

# Apply migrations to remote
npx wrangler d1 execute ucp-flower-shop --remote --file=migrations/0001_schema.sql
npx wrangler d1 execute ucp-flower-shop --remote --file=migrations/0002_seed.sql
npx wrangler d1 execute ucp-flower-shop --remote --file=migrations/0003_catalog.sql
npx wrangler d1 execute ucp-flower-shop --remote --file=migrations/0004_carts.sql
npx wrangler d1 execute ucp-flower-shop --remote --file=migrations/0005_product_options.sql

# Deploy
uv run pywrangler deploy
```

## Architecture

```
Cloudflare Workers (Pyodide / Python 3.12)
├── FastAPI (ASGI adapter built into Workers runtime)
├── Pydantic models (inline, no ucp-sdk dependency)
├── httpx (async, for webhook notifications)
└── D1 Database (serverless SQLite)
    ├── products, promotions, inventory
    ├── checkouts, orders
    └── customers, discounts, shipping_rates
```

Key design decisions:

- **Lazy app init** — FastAPI app is loaded on first request (not at module level) to stay under the 1000ms startup CPU limit
- **No `uuid.uuid4()` at module level** — Workers restricts `os.urandom()` outside request context

## Project Structure

```
src/
  entry.py              — Workers fetch handler → ASGI adapter
  app.py                — FastAPI app, exception handlers, router registration
  db.py                 — D1 database layer (all SQL queries)
  models.py             — Pydantic models for UCP schemas
  exceptions.py         — UCP error hierarchy
  enums.py              — Checkout/order status enums
  routes/
    catalog.py          — POST /catalog/search, /catalog/lookup, /catalog/product
    cart.py             — Cart CRUD + cancel
    checkout.py         — Checkout CRUD + order + webhook endpoints
    discovery.py        — GET /.well-known/ucp
    home.py             — GET / (interactive HTML page)
    platform.py         — Optional platform session/log helpers
  services/
    cart_service.py     — Cart persistence and validation
    checkout_service.py — Checkout lifecycle, payments, inventory, totals
    fulfillment_service.py — Shipping option calculation
migrations/
  0001_schema.sql       — D1 table definitions
  0002_seed.sql         — Flower shop seed data
  0003_catalog.sql      — Catalog fields (description, handle, categories)
  0004_carts.sql        — Cart tables
  0005_product_options.sql — Product options columns
```
