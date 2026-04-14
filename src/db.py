"""D1 database layer for the UCP demo server.

Replaces SQLAlchemy + aiosqlite with direct Cloudflare D1 queries.
All functions take a D1 database binding as the first argument.
"""

import datetime
import json
import uuid


def _n(val):
  """Convert None to empty string for D1 bind compatibility."""
  return val if val is not None else ""


async def get_product(db, product_id):
  """Retrieve a product by ID."""
  result = await db.prepare(
    "SELECT id, title, price, image_url FROM products WHERE id = ?"
  ).bind(product_id).first()
  return result


async def get_inventory(db, product_id):
  """Retrieve the inventory quantity for a product."""
  result = await db.prepare(
    "SELECT quantity FROM inventory WHERE product_id = ?"
  ).bind(product_id).first()
  if result:
    return result.quantity
  return None


async def get_shipping_rates(db, country_code):
  """Retrieve shipping rates for a specific country and defaults."""
  result = await db.prepare(
    "SELECT id, country_code, service_level, price, title FROM shipping_rates "
    "WHERE country_code IN (?, 'default')"
  ).bind(country_code).all()
  return result.results if result else []


async def get_discount(db, code):
  """Retrieve a discount by code."""
  result = await db.prepare(
    "SELECT code, type, value, description FROM discounts WHERE code = ?"
  ).bind(code).first()
  return result


async def get_discounts_by_codes(db, codes):
  """Retrieve multiple discounts by their codes."""
  if not codes:
    return []
  placeholders = ",".join("?" for _ in codes)
  result = await db.prepare(
    f"SELECT code, type, value, description FROM discounts WHERE code IN ({placeholders})"
  ).bind(*codes).all()
  return result.results if result else []


async def get_active_promotions(db):
  """Retrieve all active promotions."""
  result = await db.prepare(
    "SELECT id, type, min_subtotal, eligible_item_ids, description FROM promotions"
  ).all()
  rows = result.results if result else []
  # Parse eligible_item_ids from JSON string
  for row in rows:
    if row.eligible_item_ids:
      row.eligible_item_ids = json.loads(row.eligible_item_ids)
  return rows


async def get_customer(db, email):
  """Retrieve a customer by email."""
  result = await db.prepare(
    "SELECT id, name, email FROM customers WHERE email = ?"
  ).bind(email).first()
  return result


async def get_customer_addresses(db, email):
  """Retrieve addresses for a customer by email."""
  customer = await get_customer(db, email)
  if not customer:
    return []
  result = await db.prepare(
    "SELECT id, customer_id, street_address, city, state, postal_code, country "
    "FROM customer_addresses WHERE customer_id = ?"
  ).bind(customer.id).all()
  return result.results if result else []


async def save_customer_address(db, email, address):
  """Save a customer address, reusing existing ID if content matches."""
  customer = await get_customer(db, email)
  if not customer:
    customer_id = str(uuid.uuid4())
    await db.prepare(
      "INSERT INTO customers (id, name, email) VALUES (?, ?, ?)"
    ).bind(customer_id, "Unknown", email).run()
  else:
    customer_id = customer.id

  # Check for existing address with same content
  existing = await db.prepare(
    "SELECT id FROM customer_addresses "
    "WHERE customer_id = ? AND street_address = ? AND city = ? "
    "AND state = ? AND postal_code = ? AND country = ?"
  ).bind(
    customer_id,
    _n(address.get("street_address")),
    _n(address.get("address_locality")),
    _n(address.get("address_region")),
    _n(address.get("postal_code")),
    _n(address.get("address_country")),
  ).first()

  if existing:
    return existing.id

  new_id = address.get("id") or str(uuid.uuid4())
  await db.prepare(
    "INSERT INTO customer_addresses (id, customer_id, street_address, city, state, postal_code, country) "
    "VALUES (?, ?, ?, ?, ?, ?, ?)"
  ).bind(
    new_id, customer_id,
    _n(address.get("street_address")),
    _n(address.get("address_locality")),
    _n(address.get("address_region")),
    _n(address.get("postal_code")),
    _n(address.get("address_country")),
  ).run()
  return new_id


async def reserve_stock(db, product_id, quantity):
  """Atomically decrements inventory if sufficient stock exists."""
  result = await db.prepare(
    "UPDATE inventory SET quantity = quantity - ? "
    "WHERE product_id = ? AND quantity >= ?"
  ).bind(quantity, product_id, quantity).run()
  return result.meta.changes > 0


async def save_checkout(db, checkout_id, status, checkout_obj):
  """Save or update a checkout session."""
  data_json = json.dumps(checkout_obj)
  existing = await db.prepare(
    "SELECT id FROM checkouts WHERE id = ?"
  ).bind(checkout_id).first()

  if existing:
    await db.prepare(
      "UPDATE checkouts SET status = ?, data = ? WHERE id = ?"
    ).bind(status, data_json, checkout_id).run()
  else:
    await db.prepare(
      "INSERT INTO checkouts (id, status, data) VALUES (?, ?, ?)"
    ).bind(checkout_id, status, data_json).run()


async def get_checkout_session(db, checkout_id):
  """Retrieve a checkout session by ID."""
  result = await db.prepare(
    "SELECT data FROM checkouts WHERE id = ?"
  ).bind(checkout_id).first()
  if result:
    return json.loads(result.data)
  return None


async def save_order(db, order_id, order_obj):
  """Save or update an order."""
  data_json = json.dumps(order_obj)
  existing = await db.prepare(
    "SELECT id FROM orders WHERE id = ?"
  ).bind(order_id).first()

  if existing:
    await db.prepare(
      "UPDATE orders SET data = ? WHERE id = ?"
    ).bind(data_json, order_id).run()
  else:
    await db.prepare(
      "INSERT INTO orders (id, data) VALUES (?, ?)"
    ).bind(order_id, data_json).run()


async def get_order(db, order_id):
  """Retrieve an order by ID."""
  result = await db.prepare(
    "SELECT data FROM orders WHERE id = ?"
  ).bind(order_id).first()
  if result:
    return json.loads(result.data)
  return None


async def get_session_by_id(db, session_id):
  """Look up a session ID across carts, checkouts, and orders tables."""
  cart = await get_cart(db, session_id)
  if cart:
    return {"type": "cart", "data": cart}

  checkout = await get_checkout_session(db, session_id)
  if checkout:
    return {"type": "checkout", "data": checkout}

  order = await get_order(db, session_id)
  if order:
    return {"type": "order", "data": order}

  return None


async def get_request_logs_for_session(db, checkout_id, limit=50):
  """Get request logs filtered by checkout_id."""
  result = await db.prepare(
    "SELECT id, timestamp, method, url, checkout_id, payload "
    "FROM request_logs WHERE checkout_id = ? "
    "ORDER BY id DESC LIMIT ?"
  ).bind(checkout_id, limit).all()
  rows = result.results if result else []
  logs = []
  for row in rows:
    logs.append({
      "id": row.id, "timestamp": row.timestamp,
      "method": row.method, "url": row.url,
      "checkout_id": row.checkout_id,
      "payload": json.loads(row.payload) if row.payload else None,
    })
  return logs


async def log_request(db, method, url, checkout_id=None, payload=None):
  """Log an HTTP request to the database."""
  timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
  payload_json = json.dumps(payload) if payload else ""
  await db.prepare(
    "INSERT INTO request_logs (timestamp, method, url, checkout_id, payload) "
    "VALUES (?, ?, ?, ?, ?)"
  ).bind(timestamp, method, url, _n(checkout_id), _n(payload_json)).run()


async def get_idempotency_record(db, key):
  """Retrieve an idempotency record by key."""
  result = await db.prepare(
    "SELECT key, request_hash, response_status, response_body, created_at "
    "FROM idempotency_records WHERE key = ?"
  ).bind(key).first()
  if result:
    result.response_body = json.loads(result.response_body)
  return result


async def save_idempotency_record(db, key, request_hash, response_status, response_body):
  """Save a new idempotency record."""
  created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
  body_json = json.dumps(response_body)
  await db.prepare(
    "INSERT INTO idempotency_records (key, request_hash, response_status, response_body, created_at) "
    "VALUES (?, ?, ?, ?, ?)"
  ).bind(key, request_hash, response_status, body_json, created_at).run()


# --- Catalog ---


async def search_products(db, query="", price_min=None, price_max=None, limit=10, offset=0):
  """Search products by title/description with optional price filter."""
  conditions = []
  params = []

  if query:
    conditions.append("(p.title LIKE ? OR p.description LIKE ?)")
    like = f"%{query}%"
    params.extend([like, like])

  if price_min is not None:
    conditions.append("p.price >= ?")
    params.append(price_min)

  if price_max is not None:
    conditions.append("p.price <= ?")
    params.append(price_max)

  where = "WHERE " + " AND ".join(conditions) if conditions else ""

  count_result = await db.prepare(
    f"SELECT COUNT(*) as total FROM products p {where}"
  ).bind(*params).first()
  total = count_result.total if count_result else 0

  params.extend([limit, offset])
  result = await db.prepare(
    f"SELECT p.id, p.title, p.description, p.handle, p.price, p.currency, "
    f"p.image_url, p.categories, COALESCE(i.quantity, 0) as stock "
    f"FROM products p LEFT JOIN inventory i ON p.id = i.product_id "
    f"{where} ORDER BY p.title LIMIT ? OFFSET ?"
  ).bind(*params).all()

  return (result.results if result else []), total


async def lookup_products(db, ids):
  """Batch lookup products by IDs."""
  if not ids:
    return []
  placeholders = ",".join("?" for _ in ids)
  result = await db.prepare(
    f"SELECT p.id, p.title, p.description, p.handle, p.price, p.currency, "
    f"p.image_url, p.categories, COALESCE(i.quantity, 0) as stock "
    f"FROM products p LEFT JOIN inventory i ON p.id = i.product_id "
    f"WHERE p.id IN ({placeholders})"
  ).bind(*ids).all()
  return result.results if result else []


async def get_product_detail(db, product_id):
  """Get a single product with full detail."""
  result = await db.prepare(
    "SELECT p.id, p.title, p.description, p.handle, p.price, p.currency, "
    "p.image_url, p.categories, COALESCE(i.quantity, 0) as stock "
    "FROM products p LEFT JOIN inventory i ON p.id = i.product_id "
    "WHERE p.id = ?"
  ).bind(product_id).first()
  return result


async def get_product_options(db, product_id):
  """Get product options with their values, ordered by position."""
  result = await db.prepare(
    "SELECT po.name, pov.id as value_id, pov.label, pov.position "
    "FROM product_options po "
    "JOIN product_option_values pov ON po.product_id = pov.product_id AND po.name = pov.option_name "
    "WHERE po.product_id = ? "
    "ORDER BY po.position, pov.position"
  ).bind(product_id).all()
  return result.results if result else []


async def get_product_variants(db, product_id):
  """Get all variants for a product."""
  result = await db.prepare(
    "SELECT id, product_id, title, sku, price, available, options "
    "FROM product_variants WHERE product_id = ?"
  ).bind(product_id).all()
  return result.results if result else []


async def get_variant_by_id(db, variant_id):
  """Look up a single variant by its ID, returns variant + product_id."""
  result = await db.prepare(
    "SELECT id, product_id, title, sku, price, available, options "
    "FROM product_variants WHERE id = ?"
  ).bind(variant_id).first()
  return result


# --- Carts ---


async def save_cart(db, cart_id, status, cart_obj):
  """Save or update a cart session."""
  now = datetime.datetime.now(datetime.timezone.utc).isoformat()
  data_json = json.dumps(cart_obj)
  existing = await db.prepare(
    "SELECT id FROM carts WHERE id = ?"
  ).bind(cart_id).first()

  if existing:
    await db.prepare(
      "UPDATE carts SET status = ?, data = ?, updated_at = ? WHERE id = ?"
    ).bind(status, data_json, now, cart_id).run()
  else:
    await db.prepare(
      "INSERT INTO carts (id, status, data, created_at, updated_at) VALUES (?, ?, ?, ?, ?)"
    ).bind(cart_id, status, data_json, now, now).run()


async def get_cart(db, cart_id):
  """Retrieve a cart session by ID."""
  result = await db.prepare(
    "SELECT data FROM carts WHERE id = ?"
  ).bind(cart_id).first()
  if result:
    return json.loads(result.data)
  return None
