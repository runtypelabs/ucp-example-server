-- Product options and variants for interactive option selection (C3)

CREATE TABLE product_options (
  product_id TEXT NOT NULL REFERENCES products(id),
  name TEXT NOT NULL,
  position INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (product_id, name)
);

CREATE TABLE product_option_values (
  id TEXT PRIMARY KEY,
  product_id TEXT NOT NULL,
  option_name TEXT NOT NULL,
  label TEXT NOT NULL,
  position INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (product_id, option_name) REFERENCES product_options(product_id, name)
);

CREATE TABLE product_variants (
  id TEXT PRIMARY KEY,
  product_id TEXT NOT NULL REFERENCES products(id),
  title TEXT NOT NULL,
  sku TEXT,
  price INTEGER NOT NULL,
  available INTEGER NOT NULL DEFAULT 1,
  options TEXT NOT NULL DEFAULT '[]'
);

-- Bouquet Roses: Size (Small, Medium, Large) x Color (Red, Pink, White)
INSERT INTO product_options (product_id, name, position) VALUES
  ('bouquet_roses', 'Color', 0),
  ('bouquet_roses', 'Size', 1);

INSERT INTO product_option_values (id, product_id, option_name, label, position) VALUES
  ('roses_color_red', 'bouquet_roses', 'Color', 'Red', 0),
  ('roses_color_pink', 'bouquet_roses', 'Color', 'Pink', 1),
  ('roses_color_white', 'bouquet_roses', 'Color', 'White', 2),
  ('roses_size_small', 'bouquet_roses', 'Size', 'Small', 0),
  ('roses_size_medium', 'bouquet_roses', 'Size', 'Medium', 1),
  ('roses_size_large', 'bouquet_roses', 'Size', 'Large', 2);

INSERT INTO product_variants (id, product_id, title, sku, price, available, options) VALUES
  ('bouquet_roses_red_small', 'bouquet_roses', 'Red / Small', 'ROSE-RED-S', 2500, 1, '[{"name":"Color","label":"Red","id":"roses_color_red"},{"name":"Size","label":"Small","id":"roses_size_small"}]'),
  ('bouquet_roses_red_medium', 'bouquet_roses', 'Red / Medium', 'ROSE-RED-M', 3500, 1, '[{"name":"Color","label":"Red","id":"roses_color_red"},{"name":"Size","label":"Medium","id":"roses_size_medium"}]'),
  ('bouquet_roses_red_large', 'bouquet_roses', 'Red / Large', 'ROSE-RED-L', 5000, 1, '[{"name":"Color","label":"Red","id":"roses_color_red"},{"name":"Size","label":"Large","id":"roses_size_large"}]'),
  ('bouquet_roses_pink_small', 'bouquet_roses', 'Pink / Small', 'ROSE-PINK-S', 2500, 1, '[{"name":"Color","label":"Pink","id":"roses_color_pink"},{"name":"Size","label":"Small","id":"roses_size_small"}]'),
  ('bouquet_roses_pink_medium', 'bouquet_roses', 'Pink / Medium', 'ROSE-PINK-M', 3500, 1, '[{"name":"Color","label":"Pink","id":"roses_color_pink"},{"name":"Size","label":"Medium","id":"roses_size_medium"}]'),
  ('bouquet_roses_pink_large', 'bouquet_roses', 'Pink / Large', 'ROSE-PINK-L', 5000, 1, '[{"name":"Color","label":"Pink","id":"roses_color_pink"},{"name":"Size","label":"Large","id":"roses_size_large"}]'),
  ('bouquet_roses_white_small', 'bouquet_roses', 'White / Small', 'ROSE-WHT-S', 2500, 1, '[{"name":"Color","label":"White","id":"roses_color_white"},{"name":"Size","label":"Small","id":"roses_size_small"}]'),
  ('bouquet_roses_white_medium', 'bouquet_roses', 'White / Medium', 'ROSE-WHT-M', 3500, 1, '[{"name":"Color","label":"White","id":"roses_color_white"},{"name":"Size","label":"Medium","id":"roses_size_medium"}]'),
  ('bouquet_roses_white_large', 'bouquet_roses', 'White / Large', 'ROSE-WHT-L', 5000, 0, '[{"name":"Color","label":"White","id":"roses_color_white"},{"name":"Size","label":"Large","id":"roses_size_large"}]');

-- Ceramic Pot: Size (Small, Medium, Large) x Color (White, Terracotta, Blue)
INSERT INTO product_options (product_id, name, position) VALUES
  ('pot_ceramic', 'Color', 0),
  ('pot_ceramic', 'Size', 1);

INSERT INTO product_option_values (id, product_id, option_name, label, position) VALUES
  ('pot_color_white', 'pot_ceramic', 'Color', 'White', 0),
  ('pot_color_terracotta', 'pot_ceramic', 'Color', 'Terracotta', 1),
  ('pot_color_blue', 'pot_ceramic', 'Color', 'Blue', 2),
  ('pot_size_small', 'pot_ceramic', 'Size', 'Small', 0),
  ('pot_size_medium', 'pot_ceramic', 'Size', 'Medium', 1),
  ('pot_size_large', 'pot_ceramic', 'Size', 'Large', 2);

INSERT INTO product_variants (id, product_id, title, sku, price, available, options) VALUES
  ('pot_ceramic_white_small', 'pot_ceramic', 'White / Small', 'POT-WHT-S', 1000, 1, '[{"name":"Color","label":"White","id":"pot_color_white"},{"name":"Size","label":"Small","id":"pot_size_small"}]'),
  ('pot_ceramic_white_medium', 'pot_ceramic', 'White / Medium', 'POT-WHT-M', 1500, 1, '[{"name":"Color","label":"White","id":"pot_color_white"},{"name":"Size","label":"Medium","id":"pot_size_medium"}]'),
  ('pot_ceramic_white_large', 'pot_ceramic', 'White / Large', 'POT-WHT-L', 2200, 1, '[{"name":"Color","label":"White","id":"pot_color_white"},{"name":"Size","label":"Large","id":"pot_size_large"}]'),
  ('pot_ceramic_terracotta_small', 'pot_ceramic', 'Terracotta / Small', 'POT-TER-S', 1000, 1, '[{"name":"Color","label":"Terracotta","id":"pot_color_terracotta"},{"name":"Size","label":"Small","id":"pot_size_small"}]'),
  ('pot_ceramic_terracotta_medium', 'pot_ceramic', 'Terracotta / Medium', 'POT-TER-M', 1500, 1, '[{"name":"Color","label":"Terracotta","id":"pot_color_terracotta"},{"name":"Size","label":"Medium","id":"pot_size_medium"}]'),
  ('pot_ceramic_terracotta_large', 'pot_ceramic', 'Terracotta / Large', 'POT-TER-L', 2200, 1, '[{"name":"Color","label":"Terracotta","id":"pot_color_terracotta"},{"name":"Size","label":"Large","id":"pot_size_large"}]'),
  ('pot_ceramic_blue_small', 'pot_ceramic', 'Blue / Small', 'POT-BLU-S', 1200, 1, '[{"name":"Color","label":"Blue","id":"pot_color_blue"},{"name":"Size","label":"Small","id":"pot_size_small"}]'),
  ('pot_ceramic_blue_medium', 'pot_ceramic', 'Blue / Medium', 'POT-BLU-M', 1700, 1, '[{"name":"Color","label":"Blue","id":"pot_color_blue"},{"name":"Size","label":"Medium","id":"pot_size_medium"}]'),
  ('pot_ceramic_blue_large', 'pot_ceramic', 'Blue / Large', 'POT-BLU-L', 2500, 0, '[{"name":"Color","label":"Blue","id":"pot_color_blue"},{"name":"Size","label":"Large","id":"pot_size_large"}]');
