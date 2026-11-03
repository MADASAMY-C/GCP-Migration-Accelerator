# Cost Control
Check current prices at cloud.google.com/pricing; these are relative guidance, not quotes.
| Component | Risk | Control |
|---|---|---|
| Composer | always-on environment | local Airflow for dev; deploy only for demo; destroy |
| AlloyDB | always-on | `enable_alloydb=false` by default; destroy after capturing latency |
| Datastream | per-GB + running stream | enable for demo window; pause/delete stream |
| Dataflow streaming | workers run continuously | `--max_num_workers=2`; drain after demo |
| BigQuery | bytes scanned | dry-run, `maximum_bytes_billed`, keep data in the tens of GB, partition filters |
| KMS | small fixed fee | fine |
Always: budget alerts at $10/$25/$50, labels on every resource, `make tf-destroy-expensive` as the last step of any session.
