# ADR 003: BigQuery vs AlloyDB per workload
**Decision:** BigQuery for analytics, ML features and reporting. AlloyDB for point lookups of customer_360.
**Why:** Columnar scan engine vs row store with indexes. Measured p95 for single-key lookups is expected to differ by an order of magnitude (see `serving/benchmark_latency.py`; record in results.md).
**Cost:** AlloyDB is always-on; kept optional and destroyed after the demo. If lookup volume is low, Cloud SQL or BigQuery BI Engine may be enough; revisit with real traffic.
