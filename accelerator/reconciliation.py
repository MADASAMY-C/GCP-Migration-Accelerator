"""Source-vs-target migration reconciliation.

Each check in validation/checks.yaml has a Postgres (source) query and a BigQuery (target) query.
  mode: scalar -> first column of first row
  mode: keyed  -> rows of (k, v); compared key by key (e.g. per-day counts)
Results land in quality.reconciliation_results. Exit code 1 if any check fails.

Usage: python -m accelerator.reconciliation [--checks validation/checks.yaml]
Env:   PROJECT_ID, PG_DSN (e.g. "host=... dbname=retail user=... password=...")
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal


@dataclass
class CheckResult:
    name: str
    mode: str
    status: str
    source_value: str
    target_value: str
    diff: str
    details: dict = field(default_factory=dict)


def _dec(v) -> Decimal | None:
    return None if v is None else Decimal(str(v))


def compare_scalar(src, tgt, tol_abs: float = 0.0, tol_pct: float = 0.0) -> tuple[str, Decimal | None]:
    s, t = _dec(src), _dec(tgt)
    if s is None or t is None:
        return ("PASS", Decimal(0)) if s is None and t is None else ("FAIL", None)
    diff = abs(s - t)
    if diff <= Decimal(str(tol_abs)):
        return "PASS", diff
    if tol_pct and s != 0 and (diff / abs(s) * 100) <= Decimal(str(tol_pct)):
        return "PASS", diff
    return "FAIL", diff


def compare_keyed(src: dict, tgt: dict, tol_abs: float = 0.0, sample: int = 5) -> tuple[str, dict]:
    src = {str(k): _dec(v) for k, v in src.items()}
    tgt = {str(k): _dec(v) for k, v in tgt.items()}
    missing_in_target = sorted(set(src) - set(tgt))
    missing_in_source = sorted(set(tgt) - set(src))
    mismatched = [
        {"key": k, "source": str(src[k]), "target": str(tgt[k])}
        for k in sorted(set(src) & set(tgt))
        if compare_scalar(src[k], tgt[k], tol_abs)[0] == "FAIL"
    ]
    details = {
        "keys_source": len(src),
        "keys_target": len(tgt),
        "missing_in_target": len(missing_in_target),
        "missing_in_source": len(missing_in_source),
        "mismatched": len(mismatched),
        "sample_missing_in_target": missing_in_target[:sample],
        "sample_missing_in_source": missing_in_source[:sample],
        "sample_mismatched": mismatched[:sample],
    }
    ok = not (missing_in_target or missing_in_source or mismatched)
    return ("PASS" if ok else "FAIL"), details


def load_checks(path: str) -> list[dict]:
    import yaml

    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)["checks"]


def _run_pg(dsn: str, sql: str, mode: str):
    import psycopg2

    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    return rows[0][0] if mode == "scalar" else {str(r[0]): r[1] for r in rows}


def _run_bq(client, sql: str, mode: str):
    rows = list(client.query(sql).result())
    return rows[0][0] if mode == "scalar" else {str(r[0]): r[1] for r in rows}


def run(checks_path: str, pg_dsn: str, project: str) -> list[CheckResult]:
    from google.cloud import bigquery

    from accelerator import config

    client = bigquery.Client(project=project)
    results: list[CheckResult] = []
    for chk in load_checks(checks_path):
        mode = chk.get("mode", "scalar")
        tol = float(chk.get("tolerance_abs", 0))
        src = _run_pg(pg_dsn, chk["source_sql"], mode)
        tgt = _run_bq(client, config.render(chk["target_sql"], PROJECT_ID=project), mode)
        if mode == "scalar":
            status, diff = compare_scalar(src, tgt, tol, float(chk.get("tolerance_pct", 0)))
            results.append(CheckResult(chk["name"], mode, status, str(src), str(tgt), str(diff)))
        else:
            status, details = compare_keyed(src, tgt, tol)
            results.append(
                CheckResult(chk["name"], mode, status, str(len(src)), str(len(tgt)),
                            str(details["mismatched"]), details)
            )
    return results


def write_results(results: list[CheckResult], project: str, run_id: str | None = None) -> str:
    import json

    from google.cloud import bigquery

    run_id = run_id or uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for r in results:
        d = asdict(r)
        d["details"] = json.dumps(d["details"], default=str)
        rows.append({"run_id": run_id, "run_ts": now, "check_name": d["name"], "mode": d["mode"],
                     "status": d["status"], "source_value": d["source_value"],
                     "target_value": d["target_value"], "diff": d["diff"], "details": d["details"]})
    errors = bigquery.Client(project=project).insert_rows_json(f"{project}.quality.reconciliation_results", rows)
    if errors:
        raise RuntimeError(f"failed writing reconciliation results: {errors}")
    return run_id


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checks", default="validation/checks.yaml")
    args = ap.parse_args(argv)
    project = os.environ["PROJECT_ID"]
    results = run(args.checks, os.environ["PG_DSN"], project)
    run_id = write_results(results, project)
    for r in results:
        print(f"[{r.status}] {r.name}: source={r.source_value} target={r.target_value} diff={r.diff}")
    failed = [r for r in results if r.status != "PASS"]
    print(f"run_id={run_id}: {len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
