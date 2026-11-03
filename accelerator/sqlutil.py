"""Tiny helpers to run (templated) SQL files / scripts on BigQuery.

Usage: python -m accelerator.sqlutil path/to/file.sql
"""
import sys

from accelerator import config


def bq_client():
    from google.cloud import bigquery

    return bigquery.Client(project=config.PROJECT_ID, location=config.BQ_LOCATION)


def run_sql_file(path: str, **extra: str):
    with open(path, encoding="utf-8") as fh:
        sql = config.render(fh.read(), **extra)
    job = bq_client().query(sql)  # multi-statement scripts are supported
    job.result()
    return job


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    j = run_sql_file(sys.argv[1])
    print(f"done: job={j.job_id} bytes_billed={j.total_bytes_billed}")
