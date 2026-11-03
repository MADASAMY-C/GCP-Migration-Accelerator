import pytest

from accelerator.nl2sql_guard import UnsafeSQL, validate_sql

P = "proj"


def test_allows_curated_select():
    sql = "SELECT COUNT(*) FROM `proj.curated.fact_orders` WHERE EXTRACT(YEAR FROM order_ts) = 2024;"
    assert validate_sql(sql, P).startswith("SELECT")


def test_allows_cte():
    assert validate_sql("WITH a AS (SELECT 1 x) SELECT * FROM a", P)


@pytest.mark.parametrize("sql", [
    "DELETE FROM `proj.curated.t` WHERE true",
    "SELECT 1; DROP TABLE x",
    "SELECT * FROM `proj.raw.public_customers`",
    "SELECT * FROM `other.curated.t`",
    "SELECT * FROM proj.curated.t",
    "UPDATE `proj.curated.t` SET a=1",
    "",
])
def test_rejects(sql):
    with pytest.raises(UnsafeSQL):
        validate_sql(sql, P)


def test_keyword_in_string_literal_is_fine():
    assert validate_sql("SELECT * FROM `proj.curated.t` WHERE name = 'drop table'", P)
