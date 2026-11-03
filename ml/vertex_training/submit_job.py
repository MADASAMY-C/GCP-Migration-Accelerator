#!/usr/bin/env python3
"""Submit train.py to Vertex AI, register the model, and optionally run batch prediction from BigQuery.

Check current prebuilt container URIs: https://cloud.google.com/vertex-ai/docs/training/pre-built-containers
Usage: python ml/vertex_training/submit_job.py --bucket $PROJECT_ID-gma-dataflow [--batch-predict]
"""
import argparse
import os

from google.cloud import aiplatform

TRAIN_IMAGE = os.environ.get("TRAIN_IMAGE", "us-docker.pkg.dev/vertex-ai/training/tf-cpu.2-14.py310:latest")
SERVE_IMAGE = os.environ.get("SERVE_IMAGE", "us-docker.pkg.dev/vertex-ai/prediction/tf2-cpu.2-14:latest")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--batch-predict", action="store_true")
    a = ap.parse_args()
    project, region = os.environ["PROJECT_ID"], os.environ.get("REGION", "asia-south1")
    aiplatform.init(project=project, location=region, staging_bucket=f"gs://{a.bucket}")

    job = aiplatform.CustomTrainingJob(
        display_name="churn-tf", script_path="ml/vertex_training/train.py", container_uri=TRAIN_IMAGE,
        requirements=["google-cloud-bigquery", "db-dtypes", "pandas"], model_serving_container_image_uri=SERVE_IMAGE)
    model = job.run(args=[f"--project={project}"], replica_count=1, machine_type="n1-standard-4",
                    base_output_dir=f"gs://{a.bucket}/vertex/churn", sync=True)
    print("model:", model.resource_name)

    if a.batch_predict:
        # Inputs are the scoring features; predictions land in a BigQuery table that a follow-up
        # query (ml/pipeline/load_vertex_predictions.sql) merges into ml.churn_predictions.
        model.batch_predict(
            job_display_name="churn-batch", instances_format="bigquery", predictions_format="bigquery",
            bigquery_source=f"bq://{project}.ml.ml_churn_scoring", bigquery_destination_prefix=f"bq://{project}.ml",
            machine_type="n1-standard-4", starting_replica_count=1, max_replica_count=2, sync=True)


if __name__ == "__main__":
    main()
