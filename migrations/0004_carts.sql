-- Cart sessions for lightweight pre-checkout exploration
CREATE TABLE IF NOT EXISTS carts (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL DEFAULT 'active',
  data TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
