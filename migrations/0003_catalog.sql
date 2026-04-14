-- Add catalog fields to products table for v2026-04-08

ALTER TABLE products ADD COLUMN description TEXT DEFAULT '';
ALTER TABLE products ADD COLUMN handle TEXT DEFAULT '';
ALTER TABLE products ADD COLUMN currency TEXT DEFAULT 'USD';
ALTER TABLE products ADD COLUMN categories TEXT DEFAULT '[]';

-- Update seed data with descriptions, handles, and categories

UPDATE products SET
  description = 'A stunning arrangement of a dozen long-stem red roses, perfect for romantic occasions or as a luxurious gift.',
  handle = 'red-roses',
  categories = '[{"value":"Bouquets","taxonomy":"merchant"},{"value":"Roses","taxonomy":"merchant"}]'
WHERE id = 'bouquet_roses';

UPDATE products SET
  description = 'A handcrafted ceramic pot in a neutral glaze, ideal for indoor plants or as a decorative accent.',
  handle = 'ceramic-pot',
  categories = '[{"value":"Pots & Planters","taxonomy":"merchant"}]'
WHERE id = 'pot_ceramic';

UPDATE products SET
  description = 'A bright and cheerful bundle of sunflowers that brings warmth to any room.',
  handle = 'sunflower-bundle',
  categories = '[{"value":"Bouquets","taxonomy":"merchant"},{"value":"Sunflowers","taxonomy":"merchant"}]'
WHERE id = 'bouquet_sunflowers';

UPDATE products SET
  description = 'A vibrant mix of spring tulips in assorted colors, celebrating the season.',
  handle = 'spring-tulips',
  categories = '[{"value":"Bouquets","taxonomy":"merchant"},{"value":"Tulips","taxonomy":"merchant"}]'
WHERE id = 'bouquet_tulips';

UPDATE products SET
  description = 'An elegant white orchid in a minimalist pot, a sophisticated addition to any space.',
  handle = 'white-orchid',
  categories = '[{"value":"Plants","taxonomy":"merchant"},{"value":"Orchids","taxonomy":"merchant"}]'
WHERE id = 'orchid_white';

UPDATE products SET
  description = 'Fragrant gardenias with glossy green leaves, known for their intoxicating scent.',
  handle = 'gardenias',
  categories = '[{"value":"Plants","taxonomy":"merchant"},{"value":"Gardenias","taxonomy":"merchant"}]'
WHERE id = 'gardenias';
