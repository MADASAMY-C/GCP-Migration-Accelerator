# Interview Guide: telling this as a consulting engagement
**60-second pitch:** "A retailer had slow, inconsistent reports and exposed PII. I migrated their Postgres and Hive warehouse to BigQuery with CDC and batch paths, proved completeness with automated reconciliation including a cross-engine checksum, cut scanned bytes by X% through partitioning/clustering, governed PII with policy tags and masking, and added churn prediction. Everything is Terraform and CI/CD."

**Likely questions to prepare**
* Why Datastream over Debezium? (ADR 001) Why Dataflow *and* Spark? (ADR 002)
* How do you know no data was lost? Walk through counts, sums, XOR checksum, keyed diffs, and what you do on failure.
* How did you handle late/duplicate events? Windows, allowed lateness, dedupe on event_id.
* What breaks in a real migration that a tutorial hides? Network reachability, schema drift, dirty data, cutover plan, cost.
* How are policy tags kept after table rebuilds? Post-run tagging step (ADR 004).
* How would you scale this to 100x? Slot reservations, incremental Dataform models, Dataflow autoscaling, Datastream limits.
* What would you do differently? Per-workload service accounts, incremental models, VPC-SC, data contracts.

**Be honest about:** synthetic data, PoC scale, what you measured vs estimated.
