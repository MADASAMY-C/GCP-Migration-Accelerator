variable "project_id" { type = string }
variable "region" { type = string }
variable "name_prefix" { type = string }
variable "labels" { type = map(string) }

locals {
  names = ["landing", "legacy", "dataflow", "dataproc", "code"]
}

resource "google_storage_bucket" "b" {
  for_each                    = toset(local.names)
  name                        = "${var.project_id}-${var.name_prefix}-${each.key}"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true
  labels                      = var.labels

  lifecycle_rule {
    condition { age = each.key == "dataflow" || each.key == "dataproc" ? 7 : 90 }
    action { type = "Delete" }
  }
}

output "bucket_names" { value = { for k, b in google_storage_bucket.b : k => b.name } }
