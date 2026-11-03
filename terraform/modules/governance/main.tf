variable "project_id" { type = string }
variable "region" { type = string }
variable "analyst_members" { type = list(string) }
variable "privacy_members" { type = list(string) }
variable "enable_dq_scans" { type = bool }

# ---- Policy-tag taxonomy ------------------------------------------------------
resource "google_data_catalog_taxonomy" "pii" {
  region                 = var.region
  display_name           = "pii_taxonomy"
  description            = "PII classification for column-level security"
  activated_policy_types = ["FINE_GRAINED_ACCESS_CONTROL"]
}

resource "google_data_catalog_policy_tag" "pii_high" {
  taxonomy     = google_data_catalog_taxonomy.pii.id
  display_name = "pii_high"
  description  = "Email, phone: masked for analysts, raw for the privacy team"
}

# ---- Masking (data policy) -----------------------------------------------------
resource "google_bigquery_datapolicy_data_policy" "mask_high" {
  location         = var.region
  data_policy_id   = "mask_pii_high"
  policy_tag       = google_data_catalog_policy_tag.pii_high.name
  data_policy_type = "DATA_MASKING_POLICY"
  data_masking_policy {
    predefined_expression = "SHA256"
  }
}

# Two service accounts to demo "same query, different results" (also used by the NL2SQL app).
resource "google_service_account" "analyst" {
  account_id   = "gma-analyst"
  display_name = "Demo analyst (sees masked PII)"
}
resource "google_service_account" "privacy" {
  account_id   = "gma-privacy"
  display_name = "Demo privacy officer (sees raw PII)"
}

locals {
  analyst_all = concat(var.analyst_members, ["serviceAccount:${google_service_account.analyst.email}"])
  privacy_all = concat(var.privacy_members, ["serviceAccount:${google_service_account.privacy.email}"])
}

resource "google_project_iam_member" "analyst_jobs" {
  for_each = toset(local.analyst_all)
  project  = var.project_id
  role     = "roles/bigquery.jobUser"
  member   = each.key
}
resource "google_project_iam_member" "privacy_jobs" {
  for_each = toset(local.privacy_all)
  project  = var.project_id
  role     = "roles/bigquery.jobUser"
  member   = each.key
}

# Both groups read the curated dataset; only the privacy group is a fine-grained reader.
resource "google_bigquery_dataset_iam_member" "analyst_curated" {
  for_each   = toset(local.analyst_all)
  dataset_id = "curated"
  role       = "roles/bigquery.dataViewer"
  member     = each.key
}
resource "google_bigquery_dataset_iam_member" "privacy_curated" {
  for_each   = toset(local.privacy_all)
  dataset_id = "curated"
  role       = "roles/bigquery.dataViewer"
  member     = each.key
}

resource "google_bigquery_datapolicy_data_policy_iam_member" "analyst_masked" {
  for_each       = toset(local.analyst_all)
  location       = var.region
  data_policy_id = google_bigquery_datapolicy_data_policy.mask_high.data_policy_id
  role           = "roles/bigquerydatapolicy.maskedReader"
  member         = each.key
}

resource "google_data_catalog_policy_tag_iam_member" "privacy_raw" {
  for_each   = toset(local.privacy_all)
  policy_tag = google_data_catalog_policy_tag.pii_high.name
  role       = "roles/datacatalog.categoryFineGrainedReader"
  member     = each.key
}

# ---- Dataplex data-quality scans (enable after curated tables exist) ----------------
resource "google_dataplex_datascan" "dim_customer" {
  count        = var.enable_dq_scans ? 1 : 0
  location     = var.region
  data_scan_id = "dq-dim-customer"
  data {
    resource = "//bigquery.googleapis.com/projects/${var.project_id}/datasets/curated/tables/dim_customer"
  }
  execution_spec {
    trigger {
      on_demand {}
    }
  }
  data_quality_spec {
    rules {
      column    = "customer_id"
      dimension = "UNIQUENESS"
      threshold = 1.0
      uniqueness_expectation {}
    }
    rules {
      column    = "customer_id"
      dimension = "COMPLETENESS"
      threshold = 1.0
      non_null_expectation {}
    }
    rules {
      column      = "email"
      dimension   = "VALIDITY"
      threshold   = 0.99
      ignore_null = true
      regex_expectation {
        regex = "^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$"
      }
    }
  }
}

resource "google_dataplex_datascan" "fact_orders" {
  count        = var.enable_dq_scans ? 1 : 0
  location     = var.region
  data_scan_id = "dq-fact-orders"
  data {
    resource = "//bigquery.googleapis.com/projects/${var.project_id}/datasets/curated/tables/fact_orders"
  }
  execution_spec {
    trigger {
      on_demand {}
    }
  }
  data_quality_spec {
    rules {
      column    = "order_id"
      dimension = "UNIQUENESS"
      threshold = 1.0
      uniqueness_expectation {}
    }
    rules {
      column    = "payment_value"
      dimension = "VALIDITY"
      threshold = 0.999
      range_expectation {
        min_value = "0"
        max_value = "10000000"
      }
    }
    rules {
      dimension = "VALIDITY"
      threshold = 0.999
      row_condition_expectation {
        sql_expression = "order_status IN ('delivered','shipped','processing','canceled','returned')"
      }
    }
  }
}

output "taxonomy_name" { value = google_data_catalog_taxonomy.pii.display_name }
output "analyst_sa_email" { value = google_service_account.analyst.email }
output "privacy_sa_email" { value = google_service_account.privacy.email }
