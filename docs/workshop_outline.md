# Customer Workshop Deck: outline (10 slides, 45 min)
1. Why migrate: pain points and goals (from discovery)
2. Target architecture (diagram) and data layers raw/staging/curated
3. Ingestion patterns: CDC vs batch vs streaming, and when to use which
4. Proving a migration: reconciliation design (counts, sums, checksum, per-partition)
5. Modeling and performance: partitioning, clustering, MV (show benchmark table)
6. Governance: classification, policy tags, masking live demo (analyst vs privacy)
7. Data quality: rules, scores, alerts
8. Orchestration and operations: retries, backfills, SLAs, runbook
9. ML on the platform: BQML baseline vs Vertex; serving options
10. Plan, risks, cost, and next steps
Hands-on lab (optional): run the reconciliation and break a row to watch it fail.
