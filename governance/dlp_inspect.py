#!/usr/bin/env python3
"""Cloud DLP: discover PII in a BigQuery table (sampled) and save findings to quality.dlp_findings.

Usage: python governance/dlp_inspect.py --table raw.public_customers --rows 10000
Use the output to decide which columns get policy tags (governance/policy_tags.yaml).
"""
import argparse
import os

from google.cloud import dlp_v2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default="raw.public_customers")
    ap.add_argument("--rows", type=int, default=10000)
    a = ap.parse_args()
    project = os.environ["PROJECT_ID"]
    dataset, table = a.table.split(".")
    client = dlp_v2.DlpServiceClient()
    job = client.create_dlp_job(request={
        "parent": f"projects/{project}/locations/global",
        "inspect_job": {
            "storage_config": {"big_query_options": {
                "table_reference": {"project_id": project, "dataset_id": dataset, "table_id": table},
                "rows_limit": a.rows, "sample_method": "RANDOM_START"}},
            "inspect_config": {
                "info_types": [{"name": n} for n in ("EMAIL_ADDRESS", "PHONE_NUMBER", "PERSON_NAME", "INDIA_AADHAAR_INDIVIDUAL", "CREDIT_CARD_NUMBER")],
                "min_likelihood": dlp_v2.Likelihood.LIKELY, "include_quote": False},
            "actions": [{"save_findings": {"output_config": {"table": {
                "project_id": project, "dataset_id": "quality", "table_id": "dlp_findings"}}}}],
        }})
    print(f"started {job.name}; findings -> {project}.quality.dlp_findings")


if __name__ == "__main__":
    main()
