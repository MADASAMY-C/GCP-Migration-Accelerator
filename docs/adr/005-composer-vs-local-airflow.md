# ADR 005: Cloud Composer vs local Airflow
**Decision:** Develop against local Airflow; deploy to Composer 3 (small) only for the recorded demo, then destroy.
**Why:** Composer is the production answer (managed, IAM, autoscaling) but is among the most expensive components for a PoC. The DAG uses only Google provider operators so it is portable.
**Consequence for a real customer:** use Composer, or Workflows + Cloud Scheduler if orchestration needs are simple.
