variable "project_id" { type = string }
variable "region" { type = string }
variable "name" { type = string }
variable "service_account_email" { type = string }
variable "env_variables" { type = map(string) }
variable "image_version" {
  type    = string
  default = "composer-3-airflow-2"
}

resource "google_composer_environment" "this" {
  name   = var.name
  region = var.region
  config {
    software_config {
      image_version = var.image_version
      env_variables = var.env_variables
    }
    node_config {
      service_account = var.service_account_email
    }
    environment_size = "ENVIRONMENT_SIZE_SMALL"
  }
}

output "dag_gcs_prefix" { value = google_composer_environment.this.config[0].dag_gcs_prefix }
