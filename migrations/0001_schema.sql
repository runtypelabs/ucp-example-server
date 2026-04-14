-- UCP Demo Server Schema
-- Products tables
CREATE TABLE IF NOT EXISTS products (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  price INTEGER NOT NULL,
  image_url TEXT
);

CREATE TABLE IF NOT EXISTS promotions (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  min_subtotal INTEGER,
  eligible_item_ids TEXT,  -- JSON array
  description TEXT NOT NULL
);

-- Transaction tables
CREATE TABLE IF NOT EXISTS inventory (
  product_id TEXT PRIMARY KEY,
  quantity INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS customers (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);

CREATE TABLE IF NOT EXISTS customer_addresses (
  id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL REFERENCES customers(id),
  street_address TEXT,
  city TEXT,
  state TEXT,
  postal_code TEXT,
  country TEXT
);

CREATE TABLE IF NOT EXISTS checkouts (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  data TEXT NOT NULL  -- JSON
);

CREATE TABLE IF NOT EXISTS orders (
  id TEXT PRIMARY KEY,
  data TEXT NOT NULL  -- JSON
);

CREATE TABLE IF NOT EXISTS request_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  method TEXT NOT NULL,
  url TEXT NOT NULL,
  checkout_id TEXT,
  payload TEXT  -- JSON
);

CREATE TABLE IF NOT EXISTS idempotency_records (
  key TEXT PRIMARY KEY,
  request_hash TEXT NOT NULL,
  response_status INTEGER NOT NULL,
  response_body TEXT NOT NULL,  -- JSON
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payment_instruments (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  brand TEXT NOT NULL,
  last_digits TEXT NOT NULL,
  token TEXT NOT NULL,
  handler_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS discounts (
  code TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  value INTEGER NOT NULL,
  description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shipping_rates (
  id TEXT PRIMARY KEY,
  country_code TEXT NOT NULL,
  service_level TEXT NOT NULL,
  price INTEGER NOT NULL,
  title TEXT NOT NULL
);
