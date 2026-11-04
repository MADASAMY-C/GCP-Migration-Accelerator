"""SQL-based data-quality rule engine (works even without Dataplex; Dataplex scans are in Terraform).

Rules live in governance/dq_rules.yaml. Each run appends scores to quality.dq_scores and exits non-zero
if any rule scores below its threshold, so Airflow can fail/alert on it.

Usage: python -m accelerator.dq [--rules governance/dq_rules.yaml]
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import datetime, timezone

VALID_TYPES = {"not_null", "unique", "range", "regex", "set", "row_condition"}


def _lit(v) -> str:
    return "'" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'" if isinstance(v, str) else str(v)


def build_rule_sql(rule: dict, project: str) -> str:
    """Return SQL that yields (passed_rows, total_rows) for a rule."""
    rtype = rule["type"]
    if rtype not in VALID_TYPES:
        raise ValueError(f"unknown rule type {rtype!r}")
    dataset, table = rule["table"].split(".")
    tbl = f"`{project}.{dataset}.{table}`"
    col = f"`{rule['column']}`" if rule.get("column") else None
    if rtype == "unique":
        return f"SELECT COUNT(DISTINCT {col}) AS passed_rows, COUNT({col}) AS total_rows FROM {tbl}"
    if rtype == "not_null":
        cond = f"{col} IS NOT NULL"
    elif rtype == "range":
        parts = []
        if "min" in rule:
            parts.append(f"{col} >= {_lit(rule['min'])}")
        if "max" in rule:
            parts.append(f"{col} <= {_lit(rule['max'])}")
        cond = " AND ".join(parts) or "TRUE"
    elif rtype == "regex":
        cond = f"REGEXP_CONTAINS(CAST({col} AS STRING), r{_lit(rule['pattern'])})"
    elif rtype == "set":
        cond = f"{col} IN ({', '.join(_lit(v) for v in rule['values'])})"
    else:  # row_condition
        cond = f"({rule['expression']})"
    # rows where the column is NULL are judged only by not_null rules
    null_guard = f"{col} IS NULL OR " if col and rtype not in ("not_null",) else ""
    return (f"SELECT COUNTIF({null_guard}{cond}) AS passed_rows, COUNT(*) AS total_rows FROM {tbl}")


def score(passed: int, total: int) -> float:
    return 1.0 if total == 0 else round(passed / total, 6)


def evaluate(rule: dict, passed: int, total: int) -> tuple[float, str]:
    s = score(passed, total)
    return s, ("PASS" if s >= float(rule.get("threshold", 1.0)) else "FAIL")


def main(argv=None) -> int:
    import yaml
    from google.cloud import bigquery

    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", default="governance/dq_rules.yaml")
    args = ap.parse_args(argv)
    project = os.environ["PROJECT_ID"]
    client = bigquery.Client(project=project)
    with open(args.rules, encoding="utf-8") as fh:
        rules = yaml.safe_load(fh)["rules"]

    run_id, now, rows, failed = uuid.uuid4().hex[:12], datetime.now(timezone.utc).isoformat(), [], 0
    for rule in rules:
        res = next(iter(client.query(build_rule_sql(rule, project)).result()))
        s, status = evaluate(rule, int(res.passed_rows), int(res.total_rows))
        failed += status == "FAIL"
        rows.append({"run_id": run_id, "run_ts": now, "rule_name": rule["name"], "table_name": rule["table"],
                     "column_name": rule.get("column"), "rule_type": rule["type"],
                     "passed_rows": int(res.passed_rows), "total_rows": int(res.total_rows),
                     "score": s, "threshold": float(rule.get("threshold", 1.0)), "status": status})
        print(f"[{status}] {rule['name']}: {s:.4f} (threshold {rule.get('threshold', 1.0)})")
    errors = client.insert_rows_json(f"{project}.quality.dq_scores", rows)
    if errors:
        raise RuntimeError(errors)
    print(f"run_id={run_id}: {len(rules) - failed}/{len(rules)} rules passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
