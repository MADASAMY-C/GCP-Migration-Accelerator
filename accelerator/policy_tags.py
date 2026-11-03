"""Apply Data Catalog policy tags to BigQuery columns (column-level security / masking).

Dataform's CREATE OR REPLACE drops column policy tags, so this runs after every transformation run
(see the Airflow DAG). Mapping lives in governance/policy_tags.yaml.

Usage: python -m accelerator.policy_tags [--config governance/policy_tags.yaml]
"""
from __future__ import annotations

import argparse
import os
import sys


def resolve_tag_names(project: str, location: str, taxonomy_display: str) -> dict[str, str]:
    from google.cloud import datacatalog_v1

    ptm = datacatalog_v1.PolicyTagManagerClient()
    parent = f"projects/{project}/locations/{location}"
    for tax in ptm.list_taxonomies(parent=parent):
        if tax.display_name == taxonomy_display:
            return {pt.display_name: pt.name for pt in ptm.list_policy_tags(parent=tax.name)}
    raise LookupError(f"taxonomy {taxonomy_display!r} not found under {parent}")


def apply(config_path: str, project: str) -> int:
    import yaml
    from google.cloud import bigquery

    with open(config_path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    tags = resolve_tag_names(project, cfg["location"], cfg["taxonomy"])
    client = bigquery.Client(project=project)
    by_table: dict[str, dict[str, str]] = {}
    for item in cfg["columns"]:
        by_table.setdefault(item["table"], {})[item["column"]] = tags[item["tag"]]

    applied = 0
    for table_id, col_tags in by_table.items():
        table = client.get_table(f"{project}.{table_id}")
        new_schema = []
        for f in table.schema:
            if f.name in col_tags:
                pol = bigquery.PolicyTagList(names=[col_tags[f.name]])
                f = bigquery.SchemaField(f.name, f.field_type, f.mode, f.description, f.fields, policy_tags=pol)
                applied += 1
            new_schema.append(f)
        table.schema = new_schema
        client.update_table(table, ["schema"])
        print(f"tagged {table_id}: {sorted(col_tags)}")
    return applied


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="governance/policy_tags.yaml")
    args = ap.parse_args(argv)
    n = apply(args.config, os.environ["PROJECT_ID"])
    print(f"applied {n} column policy tags")
    return 0


if __name__ == "__main__":
    sys.exit(main())
