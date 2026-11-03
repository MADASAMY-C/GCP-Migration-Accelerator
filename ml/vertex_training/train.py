"""Vertex AI custom training: TensorFlow/Keras churn model on the same features as the BQML baseline.

Reads ml.ml_churn_training from BigQuery, trains an MLP, reports ROC-AUC/PR-AUC on a hold-out split,
and saves a SavedModel to AIP_MODEL_DIR (set by Vertex) or --model-dir.
"""
import argparse
import json
import os

import numpy as np
import tensorflow as tf
from google.cloud import bigquery

FEATURES = ["recency_days", "frequency", "monetary", "avg_order_value", "bad_orders"]


def load(project: str):
    df = bigquery.Client(project=project).query(
        f"SELECT {', '.join(FEATURES)}, churned FROM `{project}.ml.ml_churn_training`").to_dataframe()
    return df[FEATURES].astype("float32").fillna(0).values, df["churned"].astype("float32").values


def build(norm_layer):
    m = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(len(FEATURES),)), norm_layer,
        tf.keras.layers.Dense(32, activation="relu"), tf.keras.layers.Dropout(0.2),
        tf.keras.layers.Dense(16, activation="relu"), tf.keras.layers.Dense(1, activation="sigmoid")])
    m.compile(optimizer=tf.keras.optimizers.Adam(1e-3), loss="binary_crossentropy",
              metrics=[tf.keras.metrics.AUC(name="roc_auc"), tf.keras.metrics.AUC(curve="PR", name="pr_auc")])
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=os.environ.get("PROJECT_ID"))
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--model-dir", default=os.environ.get("AIP_MODEL_DIR", "model_out"))
    a = ap.parse_args()

    x, y = load(a.project)
    rng = np.random.default_rng(42)
    idx = rng.permutation(len(x))
    cut = int(len(x) * 0.8)
    tr, te = idx[:cut], idx[cut:]
    norm = tf.keras.layers.Normalization()
    norm.adapt(x[tr])
    model = build(norm)
    pos = max(y[tr].mean(), 1e-6)
    model.fit(x[tr], y[tr], epochs=a.epochs, batch_size=512, validation_split=0.1, verbose=2,
              class_weight={0: 1.0, 1: float((1 - pos) / pos)})
    metrics = dict(zip(model.metrics_names, model.evaluate(x[te], y[te], verbose=0)))
    print("HOLDOUT_METRICS", json.dumps(metrics))
    model.save(a.model_dir if a.model_dir.startswith("gs://") else os.path.join(a.model_dir, "saved_model"))


if __name__ == "__main__":
    main()
