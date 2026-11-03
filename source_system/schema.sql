-- Source OLTP schema (Postgres). Every table has a primary key (required by Datastream CDC).
CREATE TABLE IF NOT EXISTS customers (
  customer_id BIGINT PRIMARY KEY,
  full_name   TEXT NOT NULL,
  email       TEXT,
  phone       TEXT,
  city        TEXT,
  state       TEXT,
  created_at  TIMESTAMP NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
  product_id   BIGINT PRIMARY KEY,
  product_name TEXT NOT NULL,
  category     TEXT NOT NULL,
  price        NUMERIC(12,2) NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
  order_id     BIGINT PRIMARY KEY,
  customer_id  BIGINT NOT NULL REFERENCES customers(customer_id),
  order_status TEXT NOT NULL,
  order_ts     TIMESTAMP NOT NULL,
  updated_at   TIMESTAMP NOT NULL
);
CREATE TABLE IF NOT EXISTS order_items (
  order_item_id BIGINT PRIMARY KEY,
  order_id      BIGINT NOT NULL REFERENCES orders(order_id),
  product_id    BIGINT NOT NULL REFERENCES products(product_id),
  quantity      INT NOT NULL,
  unit_price    NUMERIC(12,2) NOT NULL
);
CREATE TABLE IF NOT EXISTS payments (
  payment_id    BIGINT PRIMARY KEY,
  order_id      BIGINT NOT NULL REFERENCES orders(order_id),
  payment_type  TEXT NOT NULL,
  payment_value NUMERIC(12,2) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_items_order ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id);
