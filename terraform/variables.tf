variable "project_id" { type = string }
variable "region" {
  type    = string
  default = "asia-south1"
}
variable "name_prefix" {
  type    = string
  default = "gma"
}
variable "labels" {
  type    = map(string)
  default = { app = "migration-accelerator", env = "dev" }
}

# --- security ---------------------------------------------------------------
variable "enable_cmek" {
  type        = bool
  default     = true
  description = "Create a KMS key and encrypt BigQuery datasets with it."
}
variable "analyst_members" {
  type        = list(string)
  default     = []
  description = "IAM members (e.g. user:a@x.com) that see MASKED PII."
}
variable "privacy_members" {
  type        = list(string)
  default     = []
  description = "IAM members that see RAW PII (fine-grained reader)."
}

# --- optional / expensive components (default OFF; turn on only for demos) ---
variable "enable_datastream" {
  type    = bool
  default = false
}
variable "enable_alloydb" {
  type    = bool
  default = false
}
variable "enable_composer" {
  type    = bool
  default = false
}
variable "enable_dq_scans" {
  type        = bool
  default     = false
  description = "Dataplex DQ scans; enable after Dataform has created curated tables."
}

# --- Datastream source (Postgres) ---------------------------------------------
variable "source_db_host" {
  type    = string
  default = ""
}
variable "source_db_port" {
  type    = number
  default = 5432
}
variable "source_db_name" {
  type    = string
  default = "retail"
}
variable "source_db_user" {
  type    = string
  default = "datastream_user"
}
variable "source_db_password" {
  type      = string
  default   = ""
  sensitive = true
}

variable "alloydb_password" {
  type      = string
  default   = ""
  sensitive = true
}
