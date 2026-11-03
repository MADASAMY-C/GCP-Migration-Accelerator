"""Dataproc Serverless (PySpark) job: bulk-migrate the Hive-style legacy warehouse to BigQuery.

Reads gs://.../legacy/orders/dt=*/part-*.csv (partition column `dt` is discovered from the path),
cleans types the same way the Beam path does, and writes raw.legacy_orders (partitioned by order_date).
Bad rows are kept in raw.legacy_orders_rejects instead of being silently dropped.

Submit:
  gcloud dataproc batches submit pyspark ingestion/spark_job/migrate_legacy.py \
    --project=$PROJECT_ID --region=$REGION --version=2.2 \
    --service-account=gma-pipeline@$PROJECT_ID.iam.gserviceaccount.com \
    --deps-bucket=$PROJECT_ID-gma-dataproc \
    -- --input=gs://$PROJECT_ID-gma-legacy/orders --project=$PROJECT_ID --temp-bucket=$PROJECT_ID-gma-dataproc
"""
import argparse

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

DATE_FORMATS = ["yyyy-MM-dd", "dd/MM/yyyy", "MM-dd-yyyy", "dd MMM yyyy"]
STATUSES = ["delivered", "shipped", "processing", "canceled", "returned"]


def clean(df):
    parsed = F.coalesce(*[F.to_date(F.col("order_date"), fmt) for fmt in DATE_FORMATS])
    status = F.lower(F.trim(F.col("status")))
    amount_str = F.regexp_replace(F.col("amount"), r"[₹$,\s]", "")
    return (
        df.withColumn("order_id_int", F.col("order_id").cast("long"))
        .withColumn("order_date_parsed", parsed)
        .withColumn("amount_num", F.when(amount_str == "", F.lit(None)).otherwise(amount_str.cast("decimal(12,2)")))
        .withColumn("_amount_blank", amount_str == "")
        .withColumn("status_clean", F.when(status.isin(STATUSES), status).otherwise(F.lit("unknown")))
        .withColumn("email_clean", F.lower(F.trim(F.col("customer_email"))))
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--temp-bucket", required=True)
    ap.add_argument("--dataset", default="raw")
    args = ap.parse_args()

    spark = (SparkSession.builder.appName("legacy-orders-migration")
             .config("spark.sql.ansi.enabled", "false").config("spark.sql.legacy.timeParserPolicy", "CORRECTED")
             .getOrCreate())
    raw = (spark.read.option("header", True).option("inferSchema", False).option("mode", "PERMISSIVE")
           .csv(args.input).withColumn("dt", F.regexp_extract(F.input_file_name(), r"dt=([0-9-]+)", 1)))
    df = clean(raw).cache()

    bad = df.filter(F.col("order_id_int").isNull() | F.col("order_date_parsed").isNull()
                    | (F.col("amount_num").isNull() & ~F.col("_amount_blank")))
    good = (df.exceptAll(bad).select(
        F.col("order_id_int").alias("order_id"), F.col("email_clean").alias("customer_email"),
        F.col("order_date_parsed").alias("order_date"), F.col("status_clean").alias("status"),
        F.col("amount_num").alias("amount"), F.col("order_date").alias("source_order_date"),
        F.col("dt"), F.current_timestamp().alias("ingest_ts")))
    rejects = bad.select(F.col("order_id"), F.col("order_date").alias("source_order_date"),
                         F.col("amount").alias("source_amount"), F.col("dt"), F.current_timestamp().alias("ingest_ts"))

    (good.write.format("bigquery").option("table", f"{args.project}.{args.dataset}.legacy_orders")
     .option("temporaryGcsBucket", args.temp_bucket).option("partitionField", "order_date")
     .option("partitionType", "DAY").mode("overwrite").save())
    (rejects.write.format("bigquery").option("table", f"{args.project}.{args.dataset}.legacy_orders_rejects")
     .option("temporaryGcsBucket", args.temp_bucket).mode("overwrite").save())
    print(f"migrated={good.count()} rejected={rejects.count()}")


if __name__ == "__main__":
    main()
