#!/usr/bin/env python3
"""Load curated.customer_360 from BigQuery into AlloyDB/Cloud SQL (via Auth Proxy) with COPY.
PII note: run as the privacy identity only if the serving layer is allowed raw PII; otherwise load masked values.

Usage: PROJECT_ID=.. PG_DSN="host=127.0.0.1 dbname=postgres user=postgres password=.." python serving/load_customer360.py
"""
import io
import os

import psycopg2
from google.cloud import bigquery

COLS = ["customer_id", "full_name", "email", "phone", "city", "state", "lifetime_orders",
        "lifetime_value", "last_order_ts", "churn_probability"]


def main():
    project = os.environ["PROJECT_ID"]
    df = bigquery.Client(project=project).query(
        f"SELECT {', '.join(COLS[:-2])}, last_order_ts AS last_order_ts, churn_probability "
        f"FROM `{project}.curated.customer_360`").to_dataframe()
    df = df[COLS]
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False)
    buf.seek(0)
    with psycopg2.connect(os.environ["PG_DSN"]) as conn, conn.cursor() as cur:
        with open(os.path.join(os.path.dirname(__file__), "alloydb_schema.sql"), encoding="utf-8") as fh:
            cur.execute(fh.read())
        cur.execute("TRUNCATE customer_360")
        cur.copy_expert(f"COPY customer_360 ({', '.join(COLS)}) FROM STDIN WITH (FORMAT csv)", buf)
    print(f"loaded {len(df)} rows")


if __name__ == "__main__":
    main()
