-- Seed data: Flower shop

-- Products
INSERT OR REPLACE INTO products (id, title, price, image_url) VALUES
  ('bouquet_roses', 'Bouquet of Red Roses', 3500, 'https://example.com/roses.jpg'),
  ('pot_ceramic', 'Ceramic Pot', 1500, 'https://example.com/pot.jpg'),
  ('bouquet_sunflowers', 'Sunflower Bundle', 2500, 'https://example.com/sunflowers.jpg'),
  ('bouquet_tulips', 'Spring Tulips', 3000, 'https://example.com/tulips.jpg'),
  ('orchid_white', 'White Orchid', 4500, 'https://example.com/orchid.jpg'),
  ('gardenias', 'Gardenias', 2000, 'https://example.com/gardenias.jpg');

-- Inventory
INSERT OR REPLACE INTO inventory (product_id, quantity) VALUES
  ('bouquet_roses', 1000),
  ('pot_ceramic', 2000),
  ('bouquet_sunflowers', 500),
  ('bouquet_tulips', 1500),
  ('orchid_white', 800),
  ('gardenias', 0);

-- Promotions
INSERT OR REPLACE INTO promotions (id, type, min_subtotal, eligible_item_ids, description) VALUES
  ('promo_1', 'free_shipping', 10000, NULL, 'Free Shipping on orders over $100'),
  ('promo_2', 'free_shipping', NULL, '["bouquet_roses"]', 'Free Shipping on Rose Bouquets');

-- Customers
INSERT OR REPLACE INTO customers (id, name, email) VALUES
  ('cust_1', 'John Doe', 'john.doe@example.com'),
  ('cust_2', 'Jane Smith', 'jane.smith@example.com'),
  ('cust_3', 'Jane Doe', 'jane.doe@example.com');

-- Customer addresses
INSERT OR REPLACE INTO customer_addresses (id, customer_id, street_address, city, state, postal_code, country) VALUES
  ('addr_1', 'cust_1', '123 Main St', 'Springfield', 'IL', '62704', 'US'),
  ('addr_2', 'cust_1', '456 Oak Ave', 'Metropolis', 'NY', '10012', 'US'),
  ('addr_3', 'cust_2', '789 Pine Ln', 'Smallville', 'KS', '66002', 'US');

-- Payment instruments
INSERT OR REPLACE INTO payment_instruments (id, type, brand, last_digits, token, handler_id) VALUES
  ('instr_1', 'card', 'Visa', '1234', 'success_token', 'mock_payment_handler'),
  ('instr_2', 'card', 'Mastercard', '5678', 'success_token', 'mock_payment_handler'),
  ('instr_fail', 'card', 'Visa', '0000', 'fail_token', 'mock_payment_handler');

-- Discounts
INSERT OR REPLACE INTO discounts (code, type, value, description) VALUES
  ('10OFF', 'percentage', 10, '10% Off'),
  ('WELCOME20', 'percentage', 20, '20% Off'),
  ('FIXED500', 'fixed_amount', 500, '$5.00 Off');

-- Shipping rates
INSERT OR REPLACE INTO shipping_rates (id, country_code, service_level, price, title) VALUES
  ('std-ship', 'default', 'standard', 500, 'Standard Shipping'),
  ('exp-ship-us', 'US', 'express', 1500, 'Express Shipping (US)'),
  ('exp-ship-intl', 'default', 'express', 2500, 'International Express');
