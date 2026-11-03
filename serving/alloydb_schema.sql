-- Low-latency "customer 360" lookup table (AlloyDB / Cloud SQL Postgres)
CREATE TABLE IF NOT EXISTS customer_360 (
  customer_id       BIGINT PRIMARY KEY,
  full_name         TEXT,
  email             TEXT,
  phone             TEXT,
  city              TEXT,
  state             TEXT,
  lifetime_orders   INT,
  lifetime_value    NUMERIC(14,2),
  last_order_ts     TIMESTAMP,
  churn_probability DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_c360_state ON customer_360(state);
