"""FastAPI serving layer. Same lookup from AlloyDB (OLTP-style) and BigQuery (analytical) so you can
measure the latency gap. Run: uvicorn serving.api.main:app --port 8080
Env: PG_DSN, PROJECT_ID
"""
import os
import time

from fastapi import FastAPI, HTTPException

app = FastAPI(title="Customer 360 serving API")
_pool = None


def pg():
    global _pool
    if _pool is None:
        from psycopg2.pool import SimpleConnectionPool

        _pool = SimpleConnectionPool(1, 5, os.environ["PG_DSN"])
    return _pool


@app.get("/healthz")
def health():
    return {"ok": True}


@app.get("/customers/{customer_id}")
def customer_alloydb(customer_id: int):
    t0, conn = time.perf_counter(), pg().getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT customer_id, full_name, city, state, lifetime_orders, lifetime_value, churn_probability "
                        "FROM customer_360 WHERE customer_id = %s", (customer_id,))
            row = cur.fetchone()
    finally:
        pg().putconn(conn)
    if not row:
        raise HTTPException(404, "customer not found")
    keys = ["customer_id", "full_name", "city", "state", "lifetime_orders", "lifetime_value", "churn_probability"]
    return {**dict(zip(keys, row)), "source": "alloydb", "latency_ms": round((time.perf_counter() - t0) * 1000, 2)}


@app.get("/bq/customers/{customer_id}")
def customer_bigquery(customer_id: int):
    from google.cloud import bigquery

    project, t0 = os.environ["PROJECT_ID"], time.perf_counter()
    job = bigquery.Client(project=project).query(
        f"SELECT customer_id, city, state, lifetime_orders, lifetime_value, churn_probability "
        f"FROM `{project}.curated.customer_360` WHERE customer_id = @id",
        job_config=bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("id", "INT64", customer_id)],
                                           use_query_cache=False))
    rows = [dict(r) for r in job.result()]
    if not rows:
        raise HTTPException(404, "customer not found")
    return {**rows[0], "source": "bigquery", "latency_ms": round((time.perf_counter() - t0) * 1000, 2)}
