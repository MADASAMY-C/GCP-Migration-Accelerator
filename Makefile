# Usage: export PROJECT_ID=... REGION=asia-south1 ; make help
SHELL := /bin/bash
REGION ?= asia-south1
P ?= $(PROJECT_ID)
PREFIX ?= gma
ROWS ?= 1000000
CUSTOMERS ?= 200000

help:            ## list targets
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-18s %s\n", $$1, $$2}'

setup:           ## python env
	python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt -r requirements-dev.txt -r requirements-beam.txt
test:            ## unit tests
	pytest -q
lint:            ## ruff
	ruff check .

# ---- source system -------------------------------------------------------
gen-data:        ## generate synthetic OLTP + messy legacy export
	python source_system/generate_data.py --orders $(ROWS) --customers $(CUSTOMERS) --out data
db-up:           ## local Postgres (logical replication on)
	docker compose -f source_system/docker-compose.yml up -d
db-load:         ## load CSVs into Postgres (set PG* env for Cloud SQL)
	./source_system/load_postgres.sh data
upload-legacy:   ## copy Hive-style export to GCS
	gsutil -m cp -r data/legacy/orders gs://$(P)-$(PREFIX)-legacy/

# ---- infra ---------------------------------------------------------------
tf-init:         ## needs STATE_BUCKET
	cd terraform && terraform init -backend-config="bucket=$(STATE_BUCKET)" -backend-config="prefix=gma"
tf-plan:
	cd terraform && terraform plan -var project_id=$(P)
tf-apply:
	cd terraform && terraform apply -var project_id=$(P)
tf-destroy-expensive: ## tear down Composer/AlloyDB/Datastream only
	cd terraform && terraform destroy -var project_id=$(P) -target=module.composer -target=module.alloydb -target=module.datastream

# ---- pipelines -----------------------------------------------------------
package:         ## build accelerator sdist for Dataflow/Composer
	python setup.py sdist -d dist
ingest-batch:    ## Beam/Dataflow: daily legacy CSV drop -> raw.legacy_orders_daily
	python ingestion/beam_batch/pipeline.py --runner=DataflowRunner --project=$(P) --region=$(REGION) \
	  --temp_location=gs://$(P)-$(PREFIX)-dataflow/tmp --setup_file=./setup.py --project_id=$(P) \
	  --service_account_email=$(PREFIX)-pipeline@$(P).iam.gserviceaccount.com \
	  --input='gs://$(P)-$(PREFIX)-legacy/orders/dt=*/part-*.csv'
ingest-spark:    ## Dataproc Serverless: bulk legacy -> raw.legacy_orders
	gcloud dataproc batches submit pyspark ingestion/spark_job/migrate_legacy.py --project=$(P) --region=$(REGION) \
	  --version=2.2 --service-account=$(PREFIX)-pipeline@$(P).iam.gserviceaccount.com --deps-bucket=$(P)-$(PREFIX)-dataproc \
	  -- --input=gs://$(P)-$(PREFIX)-legacy/orders --project=$(P) --temp-bucket=$(P)-$(PREFIX)-dataproc
stream-job:      ## Beam streaming job (Pub/Sub -> BigQuery)
	python ingestion/beam_streaming/pipeline.py --runner=DataflowRunner --project=$(P) --region=$(REGION) --streaming \
	  --temp_location=gs://$(P)-$(PREFIX)-dataflow/tmp --setup_file=./setup.py --project_id=$(P) --max_num_workers=2 \
	  --service_account_email=$(PREFIX)-pipeline@$(P).iam.gserviceaccount.com \
	  --subscription=projects/$(P)/subscriptions/$(PREFIX)-order-events-dataflow \
	  --dlq_topic=projects/$(P)/topics/$(PREFIX)-order-events-dlq
stream-publish:  ## synthetic events
	python source_system/stream_publisher.py --project $(P) --topic $(PREFIX)-order-events --rate 20 --duration 120

# ---- quality / governance ------------------------------------------------
reconcile:       ## source-vs-target checks (needs PG_DSN)
	python -m accelerator.reconciliation
dq:
	python -m accelerator.dq
tag-pii:
	python -m accelerator.policy_tags
dlp:
	python governance/dlp_inspect.py --table raw.public_customers
benchmark:       ## before/after optimization numbers
	python -m accelerator.benchmark --runs 3

# ---- ML / serving --------------------------------------------------------
bqml:
	python -m accelerator.sqlutil ml/bqml/churn_model.sql
score:
	python -m accelerator.sqlutil ml/pipeline/score_bqml.sql
vertex:
	python ml/vertex_training/submit_job.py --bucket $(P)-$(PREFIX)-dataflow
serve:
	uvicorn serving.api.main:app --port 8080
