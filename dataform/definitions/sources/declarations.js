// Tables written by Datastream (CDC), Spark and Beam. Dataform only reads them.
["public_customers", "public_orders", "public_order_items", "public_payments", "public_products",
 "legacy_orders", "legacy_orders_daily", "stream_order_events"].forEach((name) =>
  declare({ schema: "raw", name })
);
