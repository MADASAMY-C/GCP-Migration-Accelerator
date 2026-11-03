#!/usr/bin/env python3
"""Publish synthetic order events to Pub/Sub (feeds the Dataflow streaming job).

~5% of events are late (event_ts 2-8 min in the past), ~1% are malformed (-> dead-letter topic).
Usage: python source_system/stream_publisher.py --project P --topic gma-order-events --rate 20 --duration 120
"""
import argparse
import json
import random
import time
import uuid
from datetime import datetime, timedelta, timezone

TYPES = ["order_created", "payment_captured", "order_shipped", "order_canceled"]


def make_event(rng: random.Random, max_order=100_000, max_cust=20_000, late_rate=0.05, bad_rate=0.01) -> str:
    ts = datetime.now(timezone.utc)
    if rng.random() < late_rate:
        ts -= timedelta(minutes=rng.randint(2, 8))
    ev = {"event_id": str(uuid.uuid4()), "order_id": rng.randint(1, max_order),
          "customer_id": rng.randint(1, max_cust), "event_type": rng.choice(TYPES),
          "amount": round(rng.uniform(99, 9999), 2), "event_ts": ts.isoformat()}
    if rng.random() < bad_rate:
        ev.pop(rng.choice(["event_id", "order_id", "event_ts"]))
        if rng.random() < 0.5:
            return "{not json"
    return json.dumps(ev)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--topic", required=True)
    ap.add_argument("--rate", type=float, default=10, help="events per second")
    ap.add_argument("--duration", type=int, default=60, help="seconds")
    a = ap.parse_args()
    from google.cloud import pubsub_v1

    pub = pubsub_v1.PublisherClient()
    path, rng, sent = pub.topic_path(a.project, a.topic), random.Random(), 0
    end = time.time() + a.duration
    while time.time() < end:
        pub.publish(path, make_event(rng).encode("utf-8"))
        sent += 1
        time.sleep(1 / a.rate)
    print(f"published {sent} events")


if __name__ == "__main__":
    main()
