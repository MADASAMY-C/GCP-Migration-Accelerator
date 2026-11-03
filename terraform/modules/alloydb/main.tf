variable "project_id" { type = string }
variable "region" { type = string }
variable "name_prefix" { type = string }
variable "password" {
  type      = string
  sensitive = true
}

data "google_compute_network" "default" {
  name = "default"
}

resource "google_compute_global_address" "private_range" {
  name          = "${var.name_prefix}-alloydb-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = data.google_compute_network.default.id
}

resource "google_service_networking_connection" "vpc" {
  network                 = data.google_compute_network.default.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_range.name]
}

resource "google_alloydb_cluster" "this" {
  cluster_id = "${var.name_prefix}-serving"
  location   = var.region
  network_config {
    network = data.google_compute_network.default.id
  }
  initial_user {
    user     = "postgres"
    password = var.password
  }
  depends_on = [google_service_networking_connection.vpc]
}

resource "google_alloydb_instance" "primary" {
  cluster       = google_alloydb_cluster.this.name
  instance_id   = "${var.name_prefix}-primary"
  instance_type = "PRIMARY"
  machine_config {
    cpu_count = 2
  }
}

output "instance_ip" { value = google_alloydb_instance.primary.ip_address }
