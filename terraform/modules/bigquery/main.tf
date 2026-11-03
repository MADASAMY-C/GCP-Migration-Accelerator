variable "project_id" { type = string }
variable "location" { type = string }
variable "labels" { type = map(string) }
variable "kms_key_name" {
  type    = string
  default = ""
}

locals {
  datasets = {
    raw     = "Landing zone: data exactly as migrated (Datastream CDC, Spark, Beam)"
    staging = "Cleaned, typed, de-duplicated models (Dataform)"
    curated = "Business-ready star schema, features and serving tables (Dataform)"
    quality = "Reconciliation results, DQ scores, benchmark results, pipeline audit"
    ml      = "ML feature tables, models and predictions"
  }
}

resource "google_bigquery_dataset" "d" {
  for_each      = local.datasets
  dataset_id    = each.key
  location      = var.location
  description   = each.value
  labels        = var.labels
  friendly_name = each.key

  dynamic "default_encryption_configuration" {
    for_each = var.kms_key_name == "" ? [] : [1]
    content { kms_key_name = var.kms_key_name }
  }
  delete_contents_on_destroy = true
}

resource "google_bigquery_table" "reconciliation_results" {
  dataset_id          = google_bigquery_dataset.d["quality"].dataset_id
  table_id            = "reconciliation_results"
  deletion_protection = false
  time_partitioning {
    type  = "DAY"
    field = "run_ts"
  }
  schema = jsonencode([
    { name = "run_id", type = "STRING", mode = "REQUIRED" },
    { name = "run_ts", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "check_name", type = "STRING", mode = "REQUIRED" },
    { name = "mode", type = "STRING", mode = "NULLABLE" },
    { name = "status", type = "STRING", mode = "REQUIRED" },
    { name = "source_value", type = "STRING", mode = "NULLABLE" },
    { name = "target_value", type = "STRING", mode = "NULLABLE" },
    { name = "diff", type = "STRING", mode = "NULLABLE" },
    { name = "details", type = "STRING", mode = "NULLABLE" },
  ])
}

resource "google_bigquery_table" "dq_scores" {
  dataset_id          = google_bigquery_dataset.d["quality"].dataset_id
  table_id            = "dq_scores"
  deletion_protection = false
  time_partitioning {
    type  = "DAY"
    field = "run_ts"
  }
  schema = jsonencode([
    { name = "run_id", type = "STRING", mode = "REQUIRED" },
    { name = "run_ts", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "rule_name", type = "STRING", mode = "REQUIRED" },
    { name = "table_name", type = "STRING", mode = "NULLABLE" },
    { name = "column_name", type = "STRING", mode = "NULLABLE" },
    { name = "rule_type", type = "STRING", mode = "NULLABLE" },
    { name = "passed_rows", type = "INTEGER", mode = "NULLABLE" },
    { name = "total_rows", type = "INTEGER", mode = "NULLABLE" },
    { name = "score", type = "FLOAT", mode = "NULLABLE" },
    { name = "threshold", type = "FLOAT", mode = "NULLABLE" },
    { name = "status", type = "STRING", mode = "REQUIRED" },
  ])
}

resource "google_bigquery_table" "benchmark_results" {
  dataset_id          = google_bigquery_dataset.d["quality"].dataset_id
  table_id            = "benchmark_results"
  deletion_protection = false
  schema = jsonencode([
    { name = "run_ts", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "query_name", type = "STRING", mode = "REQUIRED" },
    { name = "variant", type = "STRING", mode = "REQUIRED" },
    { name = "bytes_billed", type = "INTEGER", mode = "NULLABLE" },
    { name = "slot_millis", type = "INTEGER", mode = "NULLABLE" },
    { name = "elapsed_s_median", type = "FLOAT", mode = "NULLABLE" },
    { name = "est_cost_usd", type = "FLOAT", mode = "NULLABLE" },
  ])
}

resource "google_bigquery_table" "churn_predictions" {
  dataset_id          = google_bigquery_dataset.d["ml"].dataset_id
  table_id            = "churn_predictions"
  deletion_protection = false
  time_partitioning {
    type  = "DAY"
    field = "scored_at"
  }
  schema = jsonencode([
    { name = "customer_id", type = "INTEGER", mode = "REQUIRED" },
    { name = "churn_probability", type = "FLOAT", mode = "NULLABLE" },
    { name = "model", type = "STRING", mode = "NULLABLE" },
    { name = "scored_at", type = "TIMESTAMP", mode = "REQUIRED" },
  ])
}

output "dataset_ids" { value = { for k, d in google_bigquery_dataset.d : k => d.dataset_id } }
