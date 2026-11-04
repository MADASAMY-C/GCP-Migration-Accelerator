"""Defense-in-depth SQL guard for LLM-generated queries.

This is NOT the security boundary. Real enforcement = IAM + policy tags (queries run as the end user's
identity) + maximum_bytes_billed + dry-run. The guard just rejects obviously unsafe output early.
"""
from __future__ import annotations

import re

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|drop|create|alter|truncate|grant|revoke|export|call|execute|load)\b", re.IGNORECASE
)


class UnsafeSQL(ValueError):
    pass


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return re.sub(r"(--|#)[^\n]*", " ", sql)


def validate_sql(sql: str, project: str, allowed_dataset: str = "curated") -> str:
    """Return the cleaned SQL or raise UnsafeSQL."""
    cleaned = _strip_comments(sql).strip().rstrip(";").strip()
    if not cleaned:
        raise UnsafeSQL("empty query")
    if ";" in cleaned:
        raise UnsafeSQL("multiple statements are not allowed")
    if not re.match(r"^(select|with)\b", cleaned, re.IGNORECASE):
        raise UnsafeSQL("only SELECT queries are allowed")
    # keywords are checked outside of string literals
    if FORBIDDEN.search(re.sub(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"", "''", cleaned)):
        raise UnsafeSQL("query contains a forbidden keyword")
    for ident in re.findall(r"`([^`]+)`", cleaned):
        parts = ident.split(".")
        if len(parts) == 3 and (parts[0] != project or parts[1] != allowed_dataset):
            raise UnsafeSQL(f"table outside {project}.{allowed_dataset}: {ident}")
    # unquoted project.dataset.table references are rejected: the model must backtick-quote them
    if re.search(r"\b(from|join)\s+[\w\-]+\.[\w\-]+\.[\w\-]+", cleaned, re.IGNORECASE):
        raise UnsafeSQL("table references must be backtick-quoted")
    return cleaned
