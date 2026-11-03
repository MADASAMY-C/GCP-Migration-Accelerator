import pytest

from accelerator.dq import build_rule_sql, evaluate, score


def test_sql_shapes():
    p = "proj"
    assert "COUNT(DISTINCT `customer_id`)" in build_rule_sql(
        {"table": "curated.dim_customer", "column": "customer_id", "type": "unique"}, p)
    assert "IS NOT NULL" in build_rule_sql({"table": "curated.t", "column": "c", "type": "not_null"}, p)
    sql = build_rule_sql({"table": "curated.t", "column": "c", "type": "range", "min": 0, "max": 10}, p)
    assert ">= 0" in sql and "<= 10" in sql
    assert "IN ('a', 'b')" in build_rule_sql({"table": "curated.t", "column": "c", "type": "set", "values": ["a", "b"]}, p)
    assert "REGEXP_CONTAINS" in build_rule_sql({"table": "curated.t", "column": "c", "type": "regex", "pattern": "^a"}, p)


def test_unknown_type():
    with pytest.raises(ValueError):
        build_rule_sql({"table": "a.b", "column": "c", "type": "nope"}, "p")


def test_scoring():
    assert score(0, 0) == 1.0
    assert evaluate({"threshold": 0.99}, 98, 100) == (0.98, "FAIL")
    assert evaluate({"threshold": 0.95}, 98, 100) == (0.98, "PASS")


def test_benchmark_helpers():
    from accelerator.benchmark import pct_reduction, split_queries

    q = split_queries("-- name: a\nSELECT 1\n-- name: b\nSELECT 2")
    assert q == {"a": "SELECT 1", "b": "SELECT 2"}
    assert pct_reduction(100, 25) == 75.0 and pct_reduction(0, 0) == 0.0
