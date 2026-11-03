# Work Breakdown Structure, Plan and Risks

| Phase | Work packages | Output | Exit criteria |
|---|---|---|---|
| 0 Mobilize (1-2d) | Project + budget alerts, repo, Terraform state | baseline infra | `terraform plan` clean |
| 1 Discover/Design (wk 1) | Source system, discovery doc, ADR 001-003, architecture diagram | docs | customer-style sign-off |
| 2 Migrate (wk 2-3) | Datastream CDC, Spark + Beam batch, Dataform models, reconciliation | raw/staging/curated | all reconciliation checks PASS |
| 3 Operate (wk 4) | Streaming, Airflow DAG, DQ, policy tags, DLP, CMEK | governed platform | DQ >= thresholds, masking demo |
| 4 Value (wk 5) | BQML + Vertex, AlloyDB serving, dashboard | churn model, API | AUC reported, p95 measured |
| 5 Harden (wk 6) | Benchmarks, CI/CD, cost teardown, demo video, results | results.md | reproducible from README |

## Risk register
| Risk | L | I | Mitigation |
|---|---|---|---|
| Datastream cannot reach source | M | H | Cloud SQL source with allow-list; document private connectivity option |
| Cost overrun | M | M | Budget alerts, expensive modules default off, destroy after demo |
| Silent data loss | L | H | Automated reconciliation + checksum gate in DAG |
| PII leaks to ML/serving | M | H | Policy tags re-applied after each run; features exclude PII; serving loads masked values unless approved |
| Cleaning logic diverges (Beam vs Spark) | M | M | Shared tested rules; parity report |
| Dataform drops policy tags | H | M | Post-run tagging task (ADR 004) |
| Late/duplicate streaming events | H | L | Event-time windows, allowed lateness, dedupe on event_id |
