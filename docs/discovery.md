# Discovery Document (customer: "Meridian Retail", fictional)

## 1. Current state
| Component | Detail |
|---|---|
| OLTP | Postgres 15, ~1M orders, 200k customers, 5 core tables, grows ~1.4k orders/day |
| Warehouse | Hive-style daily CSV exports on HDFS (`dt=` partitions), nightly batch, 9-12h latency |
| Reporting | Excel/SQL against Hive; finance and ops disagree on revenue |
| Security | PII (email, phone) readable by all report users, no audit |

## 2. Pain points (evidence source in brackets)
1. Slow reports: full scans of unpartitioned data [benchmark baseline].
2. Number mismatch: legacy revenue differs from OLTP on some days [`curated.legacy_report_parity`].
3. Dirty data: 4 date formats, mixed-case status, duplicates, currency symbols [Beam DLQ / Spark rejects].
4. Duplicate customers (~2%) inflate customer counts [`stg_customers.canonical_customer_id`].
5. PII exposure [DLP findings].
6. No lineage, no quality monitoring.

## 3. Requirements
| # | Requirement | Success metric |
|---|---|---|
| R1 | Migrate OLTP + history to BigQuery with proof of completeness | 100% of reconciliation checks pass |
| R2 | Near-real-time order events | event to BigQuery < 60 s p95 |
| R3 | Faster, cheaper analytics | >= 70% fewer bytes scanned on date-filtered queries |
| R4 | PII protection | analyst role sees masked email/phone; audit logs on |
| R5 | Data quality visibility | DQ score per table per run, alert on breach |
| R6 | Low-latency customer lookup | p95 < 50 ms |
| R7 | Churn prediction | ROC-AUC reported vs a baseline |
| R8 | Reproducible infra | 100% Terraform, CI/CD |

## 4. Constraints and assumptions
Region `asia-south1` (data residency). Budget cap for the PoC. Cutover is phased (parallel run, then switch).

## 5. Risks (see wbs.md for mitigations)
Source reachability for CDC, schema drift, long initial backfill, cost overrun on always-on services, PII leakage into ML features.

## 6. Out of scope
Looker semantic-layer modeling beyond a single dashboard; multi-region DR.
