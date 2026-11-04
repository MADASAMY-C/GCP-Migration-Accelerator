#!/usr/bin/env python3
from __future__ import annotations

import argparse
import statistics
import time
from urllib.error import HTTPError, URLError

import requests


def timed(url: str) -> float:
    t0 = time.perf_counter()
    r = requests.get(url, timeout=5)
    r.raise_for_status()
    return (time.perf_counter() - t0) * 1000.0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8080")
    ap.add_argument("--runs", type=int, default=50)
    ap.add_argument("--prefix", default="api/customer_360")
    ap.add_argument("--ids", default="1,2,3,4,5")
    args = ap.parse_args(argv)
    ids = [x.strip() for x in args.ids.split(",") if x.strip()]
    ms = []
    for _ in range(args.runs):
        for i in ids:
            try:
                ms.append(timed(f"{args.base}/{args.prefix}/{i}"))
            except (HTTPError, URLError, requests.RequestException):
                continue
    ms.sort()
    if ms:
        p50 = statistics.quantiles(ms, n=100)[49]
        p95 = statistics.quantiles(ms, n=100)[94]
        print(f"n={len(ms)} p50={p50:.2f}ms p95={p95:.2f}ms")
    else:
        print("no successful requests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
