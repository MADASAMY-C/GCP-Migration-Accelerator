# ADR 001: Datastream for CDC
**Status:** accepted
**Context:** Need continuous replication of 5 Postgres tables into BigQuery with minimal ops.
**Options:** (a) Datastream, (b) Debezium + Kafka/Pub/Sub, (c) periodic batch dumps.
**Decision:** Datastream, BigQuery destination in merge mode, 15 min freshness.
**Why:** Managed, native BigQuery sink (no consumer code), handles backfill + ongoing changes. Debezium gives more control but means operating Kafka Connect; batch dumps miss deletes and cannot meet R2 for tables.
**Consequences:** Source must have logical replication + PKs and be network-reachable. Freshness is minutes, not seconds, which is why order *events* use Pub/Sub + Dataflow instead.
