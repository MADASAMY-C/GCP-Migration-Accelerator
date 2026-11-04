"""Before/after benchmark: the same analytical queries against an unoptimized vs optimized table.

Runs each query in benchmarks/queries.sql (separated by lines of `-- name: <id>`), once against
curated.fact_orders_unoptimized and once against curated.fact_orders, with the query cache disabled.
Writes quality.benchmark_results and prints a markdown table for docs/results.md.

Usage: python -m accelerator.benchmark [--runs 3]
"""
from __future__ import annotations

import argparse
import os
import re
import statistics
import time
from datetime import datetime, timezone

from accelerator import config


def split_queries(text: str) -> dict[str, str]:
    parts = re.split(r"^-- name:\s*(\S+)\s*$", text, flags=re.MULTILINE)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def cost_usd(bytes_billed: int | None) -> float:
    return (bytes_billed or 0) / 1e12 * config.PRICE_PER_TB_USD


def pct_reduction(before: float, after: float) -> float:
    return 0.0 if before == 0 else round((before - after) / before * 100, 1)


def main(argv=None) -> None:
    from google.cloud import bigquery

    ap = argparse.ArgumentParser()
    ap.add_argument("--queries", default="benchmarks/queries.sql")
    ap.add_argument("--runs", type=int, default=3)
    args = ap.parse_args(argv)
    project = os.environ["PROJECT_ID"]
    client = bigquery.Client(project=project)
    with open(args.queries, encoding="utf-8") as fh:
        queries = split_queries(fh.read())

    cfg = bigquery.QueryJobConfig(use_query_cache=False)
    now, out_rows, table = datetime.now(timezone.utc).isoformat(), [], {}
    for qname, tmpl in queries.items():
        for variant, fact in (("unoptimized", "fact_orders_unoptimized"), ("optimized", "fact_orders")):
            sql = config.render(tmpl, FACT=fact, PROJECT_ID=project)
            times, job = [], None
            for _ in range(args.runs):
                t0 = time.time()
                job = client.query(sql, job_config=cfg)
                job.result()
                times.append(time.time() - t0)
            rec = {"run_ts": now, "query_name": qname, "variant": variant,
                   "bytes_billed": job.total_bytes_billed, "slot_millis": job.slot_millis,
                   "elapsed_s_median": round(statistics.median(times), 3),
                   "est_cost_usd": round(cost_usd(job.total_bytes_billed), 6)}
            out_rows.append(rec)
            table.setdefault(qname, {})[variant] = rec
    err = client.insert_rows_json(f"{project}.quality.benchmark_results", out_rows)
    if err:
        raise RuntimeError(err)

    print("| Query | Bytes billed (before -> after) | Slot-ms (before -> after) | Median time s (before -> after) | Bytes saved |")
    print("|---|---|---|---|---|")
    for q, v in table.items():
        b, a = v["unoptimized"], v["optimized"]
        print(f"| {q} | {b['bytes_billed']:,} -> {a['bytes_billed']:,} | {b['slot_millis']:,} -> {a['slot_millis']:,} "
              f"| {b['elapsed_s_median']} -> {a['elapsed_s_median']} | {pct_reduction(b['bytes_billed'], a['bytes_billed'])}% |")


if __name__ == "__main__":
    main()
