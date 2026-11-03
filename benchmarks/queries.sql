-- name: q1_daily_revenue_one_month
SELECT DATE(order_ts) d, SUM(payment_value) revenue FROM `${PROJECT_ID}.curated.${FACT}`
WHERE DATE(order_ts) BETWEEN '2024-03-01' AND '2024-03-31' GROUP BY d ORDER BY d
-- name: q2_customer_history
SELECT order_id, order_ts, payment_value FROM `${PROJECT_ID}.curated.${FACT}`
WHERE customer_id = 4242 ORDER BY order_ts DESC
-- name: q3_status_last_quarter
SELECT order_status, COUNT(*) n, SUM(payment_value) v FROM `${PROJECT_ID}.curated.${FACT}`
WHERE order_ts >= '2024-10-01' GROUP BY order_status
-- name: q4_top_customers_2024
SELECT customer_id, SUM(payment_value) v FROM `${PROJECT_ID}.curated.${FACT}`
WHERE DATE(order_ts) >= '2024-01-01' GROUP BY customer_id ORDER BY v DESC LIMIT 20
-- name: q5_running_total_window
SELECT d, revenue, SUM(revenue) OVER (ORDER BY d) AS running FROM (
  SELECT DATE(order_ts) d, SUM(payment_value) revenue FROM `${PROJECT_ID}.curated.${FACT}`
  WHERE DATE(order_ts) BETWEEN '2024-06-01' AND '2024-06-30' GROUP BY d)
-- name: q6_returned_by_payment_type
SELECT payment_type, COUNT(*) FROM `${PROJECT_ID}.curated.${FACT}`
WHERE order_status = 'returned' AND DATE(order_ts) >= '2024-07-01' GROUP BY payment_type
