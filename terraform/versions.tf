terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.35"
    }
  }
  # Remote state: terraform init -backend-config="bucket=<state-bucket>" -backend-config="prefix=gma"
  backend "gcs" {}
}

provider "google" {
  project = var.project_id
  region  = var.region
}
