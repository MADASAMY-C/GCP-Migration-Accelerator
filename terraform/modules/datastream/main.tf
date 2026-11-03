variable "project_id" { type = string }
variable "region" { type = string }
variable "name_prefix" { type = string }
variable "dataset_id" { type = string }
variable "db_host" { type = string }
variable "db_port" { type = number }
variable "db_name" { type = string }
variable "db_user" { type = string }
variable "db_password" {
  type      = string
  sensitive = true
}

resource "google_datastream_connection_profile" "source" {
  display_name          = "${var.name_prefix}-pg-source"
  location              = var.region
  connection_profile_id = "${var.name_prefix}-pg-source"
  postgresql_profile {
    hostname = var.db_host
    port     = var.db_port
    username = var.db_user
    password = var.db_password
    database = var.db_name
  }
}

resource "google_datastream_connection_profile" "dest" {
  display_name          = "${var.name_prefix}-bq-dest"
  location              = var.region
  connection_profile_id = "${var.name_prefix}-bq-dest"
  bigquery_profile {}
}

resource "google_datastream_stream" "pg_to_bq" {
  display_name  = "${var.name_prefix}-pg-to-bq"
  location      = var.region
  stream_id     = "${var.name_prefix}-pg-to-bq"
  desired_state = "RUNNING"

  source_config {
    source_connection_profile = google_datastream_connection_profile.source.id
    postgresql_source_config {
      publication      = "datastream_pub"
      replication_slot = "datastream_slot"
      include_objects {
        postgresql_schemas {
          schema = "public"
        }
      }
    }
  }

  destination_config {
    destination_connection_profile = google_datastream_connection_profile.dest.id
    bigquery_destination_config {
      data_freshness = "900s"
      single_target_dataset {
        dataset_id = "${var.project_id}:${var.dataset_id}"
      }
    }
  }

  backfill_all {}
}
