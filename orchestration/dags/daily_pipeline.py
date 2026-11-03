"""Daily batch pipeline (Cloud Composer / Airflow 2).

 ingest_legacy_drop (Dataflow) -> dataform (compile+run) -> reconcile -> apply_policy_tags -> dq_checks
                                                         -> score_churn (BQML) -> notify

* retries with exponential backoff, SLA misses and failure callbacks (email by default; swap in Slack)
* `catchup=True` + `max_active_runs=1` -> backfills are `airflow dags backfill -s 2024-01-01 -e 2024-01-07 daily_pipeline`
* Code (accelerator/) and validation/governance yaml are synced next to the DAGs by CI.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.apache.beam.operators.beam import BeamRunPythonPipelineOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator
from airflow.providers.google.cloud.operators.dataform import (
    DataformCreateCompilationResultOperator,
    DataformCreateWorkflowInvocationOperator,
)

PROJECT = os.environ.get("PROJECT_ID", "")
REGION = os.environ.get("REGION", "asia-south1")
BUCKET_PREFIX = f"{PROJECT}-gma"
DAGS_HOME = os.path.dirname(os.path.abspath(__file__))
DATAFORM_REPO = os.environ.get("DATAFORM_REPO", "gma-dataform")


def _alert(context):
    # Replace with SlackWebhookOperator / PagerDuty. Email is configured via Composer's SMTP settings.
    ti = context["task_instance"]
    print(f"ALERT: {ti.dag_id}.{ti.task_id} failed for {context['ds']}")


def _reconcile():
    from accelerator import reconciliation

    rc = reconciliation.main(["--checks", os.path.join(DAGS_HOME, "validation", "checks.yaml")])
    if rc:
        raise RuntimeError("reconciliation failed - see quality.reconciliation_results")


def _tag():
    from accelerator import policy_tags

    policy_tags.apply(os.path.join(DAGS_HOME, "governance", "policy_tags.yaml"), PROJECT)


def _dq():
    from accelerator import dq

    if dq.main(["--rules", os.path.join(DAGS_HOME, "governance", "dq_rules.yaml")]):
        raise RuntimeError("data quality rules below threshold - see quality.dq_scores")


default_args = {
    "owner": "data-eng",
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=20),
    "email_on_failure": True,
    "on_failure_callback": _alert,
    "sla": timedelta(hours=2),
}

with DAG(
    "daily_pipeline",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule="0 2 * * *",
    catchup=False,
    max_active_runs=1,
    tags=["gma", "migration"],
) as dag:
    ingest = BeamRunPythonPipelineOperator(
        task_id="ingest_legacy_drop",
        runner="DataflowRunner",
        py_file=f"gs://{BUCKET_PREFIX}-code/beam_batch/pipeline.py",
        py_requirements=["apache-beam[gcp]==2.57.0"],
        pipeline_options={
            "project": PROJECT, "region": REGION,
            "temp_location": f"gs://{BUCKET_PREFIX}-dataflow/tmp",
            "input": f"gs://{BUCKET_PREFIX}-legacy/orders/dt={{{{ ds }}}}/part-*.csv",
            "project_id": PROJECT,
            "extra_package": f"gs://{BUCKET_PREFIX}-code/accelerator-0.1.0.tar.gz",
            "write_mode": "WRITE_APPEND",
        },
        dataflow_config={"job_name": "legacy-drop-{{ ds_nodash }}", "location": REGION},
    )

    compile_df = DataformCreateCompilationResultOperator(
        task_id="dataform_compile", project_id=PROJECT, region=REGION, repository_id=DATAFORM_REPO,
        compilation_result={"git_commitish": "main"},
    )
    run_df = DataformCreateWorkflowInvocationOperator(
        task_id="dataform_run", project_id=PROJECT, region=REGION, repository_id=DATAFORM_REPO,
        workflow_invocation={"compilation_result": "{{ task_instance.xcom_pull('dataform_compile')['name'] }}"},
    )

    reconcile = PythonOperator(task_id="reconcile", python_callable=_reconcile)
    tag = PythonOperator(task_id="apply_policy_tags", python_callable=_tag)
    dq_checks = PythonOperator(task_id="dq_checks", python_callable=_dq)

    score = BigQueryInsertJobOperator(
        task_id="score_churn_bqml",
        configuration={"query": {"useLegacySql": False, "query": f"""
            INSERT INTO `{PROJECT}.ml.churn_predictions` (customer_id, churn_probability, model, scored_at)
            SELECT customer_id,
                   (SELECT p.prob FROM UNNEST(predicted_churned_probs) p WHERE p.label = 1),
                   'bqml_logreg', CURRENT_TIMESTAMP()
            FROM ML.PREDICT(MODEL `{PROJECT}.ml.churn_logreg`, TABLE `{PROJECT}.ml.ml_churn_scoring`)
        """}},
        location=REGION,
    )

    ingest >> compile_df >> run_df >> [reconcile, tag]
    tag >> dq_checks
    reconcile >> score
    dq_checks >> score
