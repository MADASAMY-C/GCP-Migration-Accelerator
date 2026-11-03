# Results (fill in from YOUR runs; do not publish unmeasured numbers)

## 1. Query performance (`make benchmark`)
| Query | Bytes billed before -> after | Slot-ms before -> after | Median time (s) before -> after | Bytes saved |
|---|---|---|---|---|
| | | | | |

Headline: "Partitioning + clustering reduced bytes scanned by __% on date-filtered queries; est. cost per run fell from $__ to $__."

## 2. Migration reconciliation (`make reconcile`)
| Check | Source | Target | Status |
|---|---|---|---|
| | | | |
Headline: "__/__ checks passed; checksum over __ rows matched."

## 3. Data quality (`make dq`)
Rules: __ | Passing: __ | Lowest score: __ (rule: __) | Legacy-vs-new revenue mismatch days: __

## 4. Streaming
Events published: __ | Landed: __ | Dead-lettered: __ | p95 end-to-end latency: __ s

## 5. ML
| Model | ROC-AUC | PR-AUC | Notes |
|---|---|---|---|
| BQML logistic regression | | | baseline |
| TensorFlow (Vertex) | | | |

## 6. Serving latency (`serving/benchmark_latency.py`)
| Store | p50 ms | p95 ms |
|---|---|---|
| AlloyDB | | |
| BigQuery | | |

## 7. Governance demo
Screenshot: same query as analyst (masked) vs privacy officer (raw).

## 8. Cost of the PoC
Total spend: $__ (from billing export).
