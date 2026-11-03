#!/usr/bin/env python3
"""Gemini natural-language-to-SQL over curated BigQuery tables, with governance respected.

The query is executed as the END USER's identity (service-account impersonation), so column policy tags /
masking apply exactly as in the console. The LLM never sees data, only schema. Guardrails:
  validate_sql (allow-list) -> dry-run -> maximum_bytes_billed -> execute as user.

Demo (same question, two identities):
  python nl2sql/app.py --as analyst "show 5 customers with their email and city"   # masked email
  python nl2sql/app.py --as privacy "show 5 customers with their email and city"   # raw email
Env: PROJECT_ID, REGION, ANALYST_SA, PRIVACY_SA, GEMINI_MODEL (default gemini-2.5-flash)
The caller needs roles/iam.serviceAccountTokenCreator on the chosen service account.
"""
import argparse
import json
import os

from accelerator.nl2sql_guard import UnsafeSQL, validate_sql

MAX_BYTES = int(os.environ.get("NL2SQL_MAX_BYTES", 1_000_000_000))  # 1 GB scan cap


def schema_context(client, project: str) -> str:
    rows = client.query(
        f"SELECT table_name, column_name, data_type, IFNULL(description, '') d "
        f"FROM `{project}.curated.INFORMATION_SCHEMA.COLUMN_FIELD_PATHS` "
        f"WHERE table_name IN ('fact_orders','dim_customer','dim_product','customer_360','mv_daily_revenue') "
        f"ORDER BY table_name, ordinal_position").result()
    tables: dict[str, list[str]] = {}
    for r in rows:
        tables.setdefault(r.table_name, []).append(f"{r.column_name} {r.data_type}" + (f" -- {r.d}" if r.d else ""))
    return "\n".join(f"`{project}.curated.{t}`(\n  " + ",\n  ".join(c) + "\n)" for t, c in tables.items())


def generate_sql(question: str, schema: str, project: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(vertexai=True, project=project, location=os.environ.get("GENAI_LOCATION", "us-central1"))
    prompt = (
        "You write BigQuery Standard SQL. Use ONLY these tables, always fully qualified with backticks "
        f"(`project.dataset.table`). Read-only SELECT, at most 100 rows. Return JSON {{\"sql\": \"...\"}}.\n\n"
        f"SCHEMA:\n{schema}\n\nQUESTION: {question}")
    resp = client.models.generate_content(
        model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"), contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0))
    return json.loads(resp.text)["sql"]


def user_client(identity: str, project: str):
    import google.auth
    from google.auth import impersonated_credentials
    from google.cloud import bigquery

    target = os.environ["ANALYST_SA" if identity == "analyst" else "PRIVACY_SA"]
    src, _ = google.auth.default()
    creds = impersonated_credentials.Credentials(
        source_credentials=src, target_principal=target,
        target_scopes=["https://www.googleapis.com/auth/bigquery"])
    return bigquery.Client(project=project, credentials=creds)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--as", dest="identity", choices=["analyst", "privacy"], default="analyst")
    a = ap.parse_args()
    from google.cloud import bigquery

    project = os.environ["PROJECT_ID"]
    bq = user_client(a.identity, project)
    sql = generate_sql(a.question, schema_context(bq, project), project)
    try:
        sql = validate_sql(sql, project)
    except UnsafeSQL as exc:
        raise SystemExit(f"blocked: {exc}\n{sql}")
    cfg = bigquery.QueryJobConfig(maximum_bytes_billed=MAX_BYTES)
    dry = bq.query(sql, job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False))
    print(f"-- as={a.identity}  est. bytes={dry.total_bytes_processed:,}\n{sql}\n")
    for row in bq.query(sql, job_config=cfg).result(max_results=20):
        print(dict(row))


if __name__ == "__main__":
    main()
