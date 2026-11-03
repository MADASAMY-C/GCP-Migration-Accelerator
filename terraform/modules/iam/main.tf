variable "project_id" { type = string }
variable "name_prefix" { type = string }
variable "buckets" { type = map(string) }

# One least-privilege service account for all data pipelines (split per-workload in a real engagement).
resource "google_service_account" "pipeline" {
  account_id   = "${var.name_prefix}-pipeline"
  display_name = "Data pipelines (Dataflow/Dataproc/Composer/Dataform)"
}

locals {
  project_roles = [
    "roles/bigquery.dataEditor", "roles/bigquery.jobUser",
    "roles/dataflow.worker", "roles/dataproc.worker",
    "roles/pubsub.subscriber", "roles/pubsub.publisher",
    "roles/composer.worker", "roles/dataform.editor",
    "roles/aiplatform.user", "roles/datacatalog.viewer",
  ]
}

resource "google_project_iam_member" "pipeline" {
  for_each = toset(local.project_roles)
  project  = var.project_id
  role     = each.key
  member   = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_storage_bucket_iam_member" "pipeline" {
  for_each = var.buckets
  bucket   = each.value
  role     = "roles/storage.objectAdmin"
  member   = "serviceAccount:${google_service_account.pipeline.email}"
}

output "pipeline_sa_email" { value = google_service_account.pipeline.email }
