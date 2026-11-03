# Runbook (end-to-end)

## 0. Before spending anything
Create a project, enable billing, **set budget alerts** ($10/$25/$50), enable billing export to BigQuery. Authenticate: `gcloud auth application-default login`.

## 1. Source system
`make gen-data ROWS=1000000` then `make db-up db-load`. Check `data/manifest.json` against `SELECT COUNT(*)` in Postgres.
For Datastream use a Cloud SQL Postgres instance instead (flag `cloudsql.logical_decoding=on`, public IP with Datastream IPs allow-listed), load the same CSVs, then run `psql -v ds_password="'...'" -f source_system/cdc_setup.sql`.

## 2. Infra
Create a state bucket, `make tf-init STATE_BUCKET=...`, `make tf-apply`. Then `make upload-legacy`.

## 3. Migration
1. Enable Datastream: set `enable_datastream=true` and `source_db_*`; apply. Wait for backfill; tables appear as `raw.public_*`.
2. `make ingest-spark` to `raw.legacy_orders`; `make ingest-batch` to `raw.legacy_orders_daily` (+DLQ tables).
3. Dataform: create a repository from `./dataform`, set `defaultProject`, run all. Fix assertion failures; they are findings, not noise.
4. `make tag-pii`, then `make reconcile` (needs PG_DSN) and `make dq`.

## 4. Break it on purpose (great for the demo)
`UPDATE orders SET order_status='delivered' WHERE order_id=1;` in the source before CDC catches up, or edit a BigQuery row; re-run `make reconcile` and show the checksum check failing while counts still pass.

## 5. Streaming
`make stream-job`; `make stream-publish`; query `raw.stream_order_events` and `raw.stream_revenue_1min`; pull bad messages from the DLQ inspect subscription. **Drain the Dataflow job afterwards.**

## 6. Performance
`make benchmark` and paste the table into `docs/results.md`.

## 7. ML and serving
`make bqml score`; re-run Dataform (customer_360 picks up predictions); optional `make vertex`; enable AlloyDB, `serving/load_customer360.py`, `make serve`, `python serving/benchmark_latency.py`.

## 8. Governance demo
Run the same SELECT on `curated.dim_customer` as analyst SA vs privacy SA (impersonation), or use `nl2sql/app.py --as ...`. Grant yourself `roles/iam.serviceAccountTokenCreator` on both SAs first.

## 9. Teardown
`make tf-destroy-expensive`; drain/cancel Dataflow; delete Datastream stream; `terraform destroy` for everything when done. Postgres replication slots keep WAL growing, so drop `datastream_slot` if you stop the stream.

## Troubleshooting
| Symptom | Likely cause |
|---|---|
| Datastream "cannot connect" | firewall/allow-list; wrong host |
| Datastream backfill empty | publication not created or tables lack PKs |
| Dataform: `churn_predictions` not found | apply Terraform (creates the empty table) |
| Policy-tag apply fails | taxonomy region differs from `policy_tags.yaml` |
| Beam job import error | missing `--setup_file=./setup.py` |
