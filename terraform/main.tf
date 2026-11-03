locals {
  apis = [
    "bigquery.googleapis.com", "dataflow.googleapis.com", "dataproc.googleapis.com",
    "datastream.googleapis.com", "pubsub.googleapis.com", "composer.googleapis.com",
    "alloydb.googleapis.com", "servicenetworking.googleapis.com", "compute.googleapis.com",
    "dataform.googleapis.com", "dataplex.googleapis.com", "datacatalog.googleapis.com",
    "bigquerydatapolicy.googleapis.com", "dlp.googleapis.com", "cloudkms.googleapis.com",
    "aiplatform.googleapis.com", "iam.googleapis.com", "cloudbuild.googleapis.com",
    "storage.googleapis.com", "sqladmin.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  service            = each.key
  disable_on_destroy = false
}

module "storage" {
  source      = "./modules/storage"
  project_id  = var.project_id
  region      = var.region
  name_prefix = var.name_prefix
  labels      = var.labels
  depends_on  = [google_project_service.apis]
}

module "kms" {
  count      = var.enable_cmek ? 1 : 0
  source     = "./modules/kms"
  project_id = var.project_id
  region     = var.region
  name       = "${var.name_prefix}-bq"
  depends_on = [google_project_service.apis]
}

module "iam" {
  source      = "./modules/iam"
  project_id  = var.project_id
  name_prefix = var.name_prefix
  buckets     = module.storage.bucket_names
  depends_on  = [google_project_service.apis]
}

module "bigquery" {
  source       = "./modules/bigquery"
  project_id   = var.project_id
  location     = var.region
  labels       = var.labels
  kms_key_name = var.enable_cmek ? module.kms[0].key_id : ""
  depends_on   = [google_project_service.apis]
}

module "pubsub" {
  source      = "./modules/pubsub"
  project_id  = var.project_id
  name_prefix = var.name_prefix
  labels      = var.labels
  depends_on  = [google_project_service.apis]
}

module "governance" {
  source          = "./modules/governance"
  project_id      = var.project_id
  region          = var.region
  analyst_members = var.analyst_members
  privacy_members = var.privacy_members
  enable_dq_scans = var.enable_dq_scans
  depends_on      = [google_project_service.apis, module.bigquery]
}

module "datastream" {
  count       = var.enable_datastream ? 1 : 0
  source      = "./modules/datastream"
  project_id  = var.project_id
  region      = var.region
  name_prefix = var.name_prefix
  dataset_id  = module.bigquery.dataset_ids["raw"]
  db_host     = var.source_db_host
  db_port     = var.source_db_port
  db_name     = var.source_db_name
  db_user     = var.source_db_user
  db_password = var.source_db_password
  depends_on  = [google_project_service.apis]
}

module "alloydb" {
  count       = var.enable_alloydb ? 1 : 0
  source      = "./modules/alloydb"
  project_id  = var.project_id
  region      = var.region
  name_prefix = var.name_prefix
  password    = var.alloydb_password
  depends_on  = [google_project_service.apis]
}

module "composer" {
  count                 = var.enable_composer ? 1 : 0
  source                = "./modules/composer"
  project_id            = var.project_id
  region                = var.region
  name                  = "${var.name_prefix}-composer"
  service_account_email = module.iam.pipeline_sa_email
  env_variables         = { PROJECT_ID = var.project_id, REGION = var.region }
  depends_on            = [google_project_service.apis, module.iam]
}
