# ADR 002: Dataflow vs Dataproc Serverless
**Status:** accepted
**Decision:** Dataflow (Beam) for streaming and recurring small batch; Dataproc Serverless (Spark) for the one-off bulk legacy migration.
**Why:** Beam gives event-time windowing, late-data handling, DLQ side outputs and autoscaling for streaming. The legacy estate is Spark/Hive-shaped: existing Spark SQL/skills port with least rewrite, and serverless removes cluster management.
**Trade-offs:** Two codebases that must share cleaning rules, so the rules are unit-tested in `accelerator/transforms.py` and mirrored in Spark; reconciliation catches drift between them.
