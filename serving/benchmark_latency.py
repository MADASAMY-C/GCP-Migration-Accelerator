#!/usr/bin/env python3
"""Compare p50/p95 latency: AlloyDB endpoint vs BigQuery endpoint. Usage: python serving/benchmark_latency.py --n 200"""
import argparse
import json
import random
import statistics
import urllib.request


def timed(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)["latency_ms"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8080")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--max-id", type=int, default=20000)
    a = ap.parse_args()
    ids = [random.randint(1, a.max_id) for _ in range(a.n)]
    for label, prefix in (("alloydb", "customers"), ("bigquery", "bq/customers")):
        ms = []
        for i in ids:
            try:
                ms.append(timed(f"{a.base}/{prefix}/{i}"))
            except Exception:  # 404 for deduped ids is expected
                continue
        ms.sort()
        if ms:
            print(f"{label:9s} n={len(ms)} p50={statistics.median(ms):.1f}ms p95={ms[int(len(ms) * .95) - 1]:.1f}ms")


if __name__ == "__main__":
    main()
