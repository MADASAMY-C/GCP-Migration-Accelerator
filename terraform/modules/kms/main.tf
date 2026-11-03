variable "project_id" { type = string }
variable "region" { type = string }
variable "name" { type = string }

resource "google_kms_key_ring" "ring" {
  name     = "${var.name}-ring"
  location = var.region
}

resource "google_kms_crypto_key" "key" {
  name            = "${var.name}-key"
  key_ring        = google_kms_key_ring.ring.id
  rotation_period = "7776000s" # 90 days
}

# BigQuery's service agent must be able to use the key
data "google_bigquery_default_service_account" "bq" {
  project = var.project_id
}

resource "google_kms_crypto_key_iam_member" "bq" {
  crypto_key_id = google_kms_crypto_key.key.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:${data.google_bigquery_default_service_account.bq.email}"
}

output "key_id" {
  value      = google_kms_crypto_key.key.id
  depends_on = [google_kms_crypto_key_iam_member.bq]
}
