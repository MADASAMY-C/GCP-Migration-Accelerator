"""Streaming Beam/Dataflow pipeline: Pub/Sub order events -> BigQuery.

Branches
  1. raw events      -> raw.stream_order_events            (event-time stamped)
  2. 1-min windows   -> raw.stream_revenue_1min            (fixed windows, 5-min allowed lateness,
                                                            late firings re-emit corrected panes)
  3. invalid msgs    -> Pub/Sub dead-letter topic (raw bytes + error attribute)
Duplicate deliveries are harmless: staging de-duplicates on event_id (Pub/Sub is at-least-once).

Run:
  python ingestion/beam_streaming/pipeline.py --runner=DataflowRunner --project=$PROJECT_ID --region=$REGION \
    --streaming --temp_location=gs://$PROJECT_ID-gma-dataflow/tmp --setup_file=./setup.py \
    --subscription=projects/$PROJECT_ID/subscriptions/gma-order-events-dataflow \
    --dlq_topic=projects/$PROJECT_ID/topics/gma-order-events-dlq --project_id=$PROJECT_ID \
    --service_account_email=gma-pipeline@$PROJECT_ID.iam.gserviceaccount.com --max_num_workers=2
"""
import argparse
from decimal import Decimal

import apache_beam as beam
from apache_beam.io.gcp.bigquery import BigQueryDisposition, WriteToBigQuery
from apache_beam.io.gcp.pubsub import PubsubMessage, ReadFromPubSub, WriteToPubSub
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions
from apache_beam.transforms import window
from apache_beam.transforms.trigger import AccumulationMode, AfterCount, AfterWatermark

from accelerator.transforms import AGG_SCHEMA, EVENT_SCHEMA, parse_order_event


class ParseEvent(beam.DoFn):
    def process(self, payload):
        try:
            ev = parse_order_event(payload)
        except Exception as exc:  # noqa: BLE001
            yield beam.pvalue.TaggedOutput("dead_letter", PubsubMessage(payload, {"error": str(exc)[:200]}))
            return
        yield window.TimestampedValue(ev, ev["event_epoch"])


class FormatWindow(beam.DoFn):
    def process(self, kv, win=beam.DoFn.WindowParam):
        event_type, (count, amount) = kv
        yield {"window_start": win.start.to_utc_datetime().isoformat(), "window_end": win.end.to_utc_datetime().isoformat(),
               "event_type": event_type, "event_count": count, "amount_sum": str(amount)}


class SumCount(beam.CombineFn):
    def create_accumulator(self):
        return 0, Decimal(0)

    def add_input(self, acc, ev):
        return acc[0] + 1, acc[1] + Decimal(ev["amount"] or "0")

    def merge_accumulators(self, accs):
        return sum(a[0] for a in accs), sum((a[1] for a in accs), Decimal(0))

    def extract_output(self, acc):
        return acc


def run(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--subscription", required=True)
    ap.add_argument("--dlq_topic", required=True)
    ap.add_argument("--project_id", required=True)
    ap.add_argument("--window_seconds", type=int, default=60)
    ap.add_argument("--allowed_lateness_seconds", type=int, default=300)
    args, beam_args = ap.parse_known_args(argv)
    opts = PipelineOptions(beam_args, save_main_session=True)
    opts.view_as(StandardOptions).streaming = True

    with beam.Pipeline(options=opts) as p:
        parsed = (
            p
            | "Read" >> ReadFromPubSub(subscription=args.subscription)
            | "Parse" >> beam.ParDo(ParseEvent()).with_outputs("dead_letter", main="valid")
        )
        (parsed.valid
         | "ToRow" >> beam.Map(lambda e: {k: v for k, v in e.items() if k != "event_epoch"})
         | "WriteRaw" >> WriteToBigQuery(
             f"{args.project_id}:raw.stream_order_events", schema=EVENT_SCHEMA,
             create_disposition=BigQueryDisposition.CREATE_IF_NEEDED,
             write_disposition=BigQueryDisposition.WRITE_APPEND))
        (parsed.valid
         | "Window" >> beam.WindowInto(
             window.FixedWindows(args.window_seconds),
             trigger=AfterWatermark(late=AfterCount(1)),
             allowed_lateness=args.allowed_lateness_seconds,
             accumulation_mode=AccumulationMode.DISCARDING)
         | "KeyByType" >> beam.Map(lambda e: (e["event_type"], e))
         | "Aggregate" >> beam.CombinePerKey(SumCount())
         | "FormatWindow" >> beam.ParDo(FormatWindow())
         | "WriteAgg" >> WriteToBigQuery(
             f"{args.project_id}:raw.stream_revenue_1min", schema=AGG_SCHEMA,
             create_disposition=BigQueryDisposition.CREATE_IF_NEEDED,
             write_disposition=BigQueryDisposition.WRITE_APPEND))
        parsed.dead_letter | "WriteDLQ" >> WriteToPubSub(args.dlq_topic, with_attributes=True)


if __name__ == "__main__":
    run()
