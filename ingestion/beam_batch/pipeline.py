"""Batch Beam/Dataflow pipeline: legacy Hive-style CSV drops (GCS) -> BigQuery raw.legacy_orders_daily.

* parses/cleans every line with accelerator.transforms (4 date formats, currency symbols, status casing)
* invalid rows never fail the job: they go to a dead-letter table with the error reason
* Beam metrics: rows_ok / rows_dead_letter

Run (Dataflow):
  python ingestion/beam_batch/pipeline.py --runner=DataflowRunner --project=$PROJECT_ID --region=$REGION \
     --temp_location=gs://$PROJECT_ID-gma-dataflow/tmp --setup_file=./setup.py \
     --service_account_email=gma-pipeline@$PROJECT_ID.iam.gserviceaccount.com \
     --input='gs://$PROJECT_ID-gma-legacy/orders/dt=*/part-*.csv' --project_id=$PROJECT_ID
Run (local test): --runner=DirectRunner with a local --input glob and --output_table pointing at a sandbox dataset.
"""
import argparse

import apache_beam as beam
from apache_beam.io.gcp.bigquery import BigQueryDisposition, WriteToBigQuery
from apache_beam.metrics import Metrics
from apache_beam.options.pipeline_options import PipelineOptions

from accelerator.transforms import LEGACY_DLQ_SCHEMA, LEGACY_SCHEMA, parse_legacy_order_line, utcnow_iso


class ParseLegacyOrder(beam.DoFn):
    def __init__(self):
        self.ok = Metrics.counter("legacy", "rows_ok")
        self.dead = Metrics.counter("legacy", "rows_dead_letter")

    def process(self, line):
        if not line.strip():
            return
        try:
            row = parse_legacy_order_line(line)
        except Exception as exc:  # noqa: BLE001 - every failure must be routed, never raised
            self.dead.inc()
            yield beam.pvalue.TaggedOutput("dead_letter", {"raw_line": line, "error": str(exc), "ingest_ts": utcnow_iso()})
        else:
            self.ok.inc()
            yield row


def run(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--project_id", required=True)
    ap.add_argument("--output_table", default=None)
    ap.add_argument("--dlq_table", default=None)
    ap.add_argument("--write_mode", default="WRITE_TRUNCATE", choices=["WRITE_TRUNCATE", "WRITE_APPEND"])
    args, beam_args = ap.parse_known_args(argv)
    out = args.output_table or f"{args.project_id}:raw.legacy_orders_daily"
    dlq = args.dlq_table or f"{args.project_id}:raw.legacy_orders_daily_dlq"

    with beam.Pipeline(options=PipelineOptions(beam_args, save_main_session=True)) as p:
        res = (
            p
            | "Read" >> beam.io.ReadFromText(args.input, skip_header_lines=1)
            | "Parse" >> beam.ParDo(ParseLegacyOrder()).with_outputs("dead_letter", main="valid")
        )
        res.valid | "WriteValid" >> WriteToBigQuery(
            out, schema=LEGACY_SCHEMA, create_disposition=BigQueryDisposition.CREATE_IF_NEEDED,
            write_disposition=getattr(BigQueryDisposition, args.write_mode))
        res.dead_letter | "WriteDLQ" >> WriteToBigQuery(
            dlq, schema=LEGACY_DLQ_SCHEMA, create_disposition=BigQueryDisposition.CREATE_IF_NEEDED,
            write_disposition=getattr(BigQueryDisposition, args.write_mode))


if __name__ == "__main__":
    run()
