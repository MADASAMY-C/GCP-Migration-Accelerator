# ADR 004: Dataform vs dbt
**Decision:** Dataform.
**Why:** Native to GCP (no extra infra, IAM-integrated, Composer operators, lineage in Dataplex/BigQuery). dbt has a larger ecosystem and community packages; choose it when the customer already runs dbt or is multi-warehouse.
**Consequences:** Dataform CREATE OR REPLACE drops column policy tags, so tags are re-applied by `accelerator.policy_tags` after each run.
