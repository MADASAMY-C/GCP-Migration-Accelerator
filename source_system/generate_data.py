#!/usr/bin/env python3
"""Synthetic retail data generator (stdlib only, deterministic, streams to disk).

Produces two things:
  <out>/oltp/*.csv                       -> load into Postgres (the "on-prem OLTP" source; Datastream CDC path)
  <out>/legacy/orders/dt=YYYY-MM-DD/...  -> Hive-style *messy* CSV export of the legacy warehouse (batch path)
  <out>/manifest.json                    -> expected row counts / totals, used to sanity-check reconciliation

Deliberate mess (so the migration has real work to do):
  customers: ~dup_rate duplicate people (same email, different id/case), ~4% null emails, ~10% null phones (PII)
  legacy:    4 date formats, inconsistent status casing, currency symbols/commas in amount, ~1% null amounts,
             ~0.3% duplicate rows, ~0.2% unparseable rows (DLQ candidates), ~0.5% amounts that drifted vs OLTP

Usage: python source_system/generate_data.py --orders 1000000 --customers 200000 --out data
"""
import argparse
import csv
import json
import os
import random
from array import array
from datetime import date, datetime, time, timedelta

FIRST = ["Aarav", "Vivaan", "Aditya", "Diya", "Ananya", "Ishaan", "Meera", "Kabir", "Saanvi", "Rohan",
         "Priya", "Arjun", "Neha", "Karan", "Isha", "Rahul", "Sneha", "Vikram", "Pooja", "Amit"]
LAST = ["Sharma", "Iyer", "Reddy", "Nair", "Gupta", "Patel", "Singh", "Das", "Mehta", "Rao",
        "Kapoor", "Menon", "Joshi", "Bose", "Chopra", "Pillar", "Kulkarni", "Shetty"]
CITIES = [("Bengaluru", "KA"), ("Chennai", "TN"), ("Hyderabad", "TS"), ("Gurugram", "HR"),
          ("Mumbai", "MH"), ("Pune", "MH"), ("Kolkata", "WB"), ("Delhi", "DL")]
CATEGORIES = ["electronics", "fashion", "home", "beauty", "sports", "books", "grocery", "toys"]
STATUSES = ["delivered", "shipped", "processing", "canceled", "returned"]
STATUS_W = [0.80, 0.07, 0.05, 0.05, 0.03]
PAY_TYPES = ["upi", "credit_card", "debit_card", "cod", "wallet"]
DOMAINS = ["gmail.com", "yahoo.in", "outlook.com", "example.org", "mail.com"]
DATE_FMTS = ["%Y-%m-%d", "%d/%m/%Y", "%m-%d-%Y", "%d %b %Y"]
DATE_W = [0.80, 0.10, 0.07, 0.03]
START, END = date(2022, 1, 1), date(2024, 12, 31)


def name_for(cid: int) -> str:
    return f"{FIRST[(cid * 7) % len(FIRST)]} {LAST[(cid * 13) % len(LAST)]}"


def email_for(cid: int) -> str:
    return f"user{cid}@{DOMAINS[cid % len(DOMAINS)]}"


def cents(c: int) -> str:
    return f"{c // 100}.{c % 100:02d}"


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--orders", type=int, default=100_000)
    ap.add_argument("--customers", type=int, default=20_000)
    ap.add_argument("--products", type=int, default=2_000)
    ap.add_argument("--dup-rate", type=float, default=0.02)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="data")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)

    oltp, legacy_root = os.path.join(a.out, "oltp"), os.path.join(a.out, "legacy", "orders")
    os.makedirs(oltp, exist_ok=True)
    os.makedirs(legacy_root, exist_ok=True)

    def writer(name, header):
        fh = open(os.path.join(oltp, name), "w", newline="", encoding="utf-8")
        w = csv.writer(fh)
        w.writerow(header)
        return fh, w

    # ---- customers (with duplicates + PII) -------------------------------------------------
    base_of = array("I", [0]) * (a.customers + 1)  # canonical person id per customer row
    fh, w = writer("customers.csv", ["customer_id", "full_name", "email", "phone", "city", "state", "created_at"])
    dups = 0
    for cid in range(1, a.customers + 1):
        base = cid
        if cid > 1 and rng.random() < a.dup_rate:
            for _ in range(10):
                cand = rng.randint(1, cid - 1)
                if base_of[cand] == cand and cand % 25 != 0:
                    base = cand
                    break
        base_of[cid] = base
        if base != cid:
            dups += 1
        email = None if base % 25 == 0 else email_for(base)
        if email and base != cid:
            email = rng.choice([email.upper(), f" {email}", email])  # dirty variants of the same person
        city, state = CITIES[cid % len(CITIES)]
        phone = None if rng.random() < 0.10 else f"+91{rng.randint(6_000_000_000, 9_999_999_999)}"
        created = datetime.combine(START - timedelta(days=rng.randint(1, 365)), time(rng.randint(0, 23), rng.randint(0, 59)))
        w.writerow([cid, name_for(base), email, phone, city, state, created.isoformat(sep=" ")])
    fh.close()

    # ---- products ---------------------------------------------------------------------------
    prices = [int(max(99, rng.lognormvariate(6.2, 0.9))) for _ in range(a.products)]  # whole rupees
    price_cents = [p * 100 for p in prices]
    fh, w = writer("products.csv", ["product_id", "product_name", "category", "price"])
    for pid in range(1, a.products + 1):
        w.writerow([pid, f"Product {pid}", CATEGORIES[pid % len(CATEGORIES)], cents(price_cents[pid - 1])])
    fh.close()

    # ---- orders / items / payments + legacy export (iterate by day => one open file at a time) --
    fo, wo = writer("orders.csv", ["order_id", "customer_id", "order_status", "order_ts", "updated_at"])
    fi, wi = writer("order_items.csv", ["order_item_id", "order_id", "product_id", "quantity", "unit_price"])
    fp, wp = writer("payments.csv", ["payment_id", "order_id", "payment_type", "payment_value"])
    days = (END - START).days + 1
    base_n, rem = divmod(a.orders, days)
    order_id = item_id = pay_id = 0
    total_cents = 0
    stats = {"legacy_rows": 0, "legacy_bad_rows": 0, "legacy_dup_rows": 0, "legacy_drifted": 0}

    for d in range(days):
        day = START + timedelta(days=d)
        n = base_n + (1 if d < rem else 0)
        part_dir = os.path.join(legacy_root, f"dt={day.isoformat()}")
        os.makedirs(part_dir, exist_ok=True)
        lf = open(os.path.join(part_dir, "part-0000.csv"), "w", newline="", encoding="utf-8")
        lw = csv.writer(lf)
        lw.writerow(["order_id", "customer_email", "order_date", "status", "amount"])
        for _ in range(n):
            order_id += 1
            cid = rng.randint(1, a.customers)
            ts = datetime.combine(day, time(0, 0)) + timedelta(seconds=rng.randint(0, 86399))
            status = rng.choices(STATUSES, STATUS_W)[0]
            order_cents = 0
            for _ in range(rng.randint(1, 4)):
                item_id += 1
                pid, qty = rng.randint(1, a.products), rng.randint(1, 3)
                order_cents += price_cents[pid - 1] * qty
                wi.writerow([item_id, order_id, pid, qty, cents(price_cents[pid - 1])])
            pay_id += 1
            wp.writerow([pay_id, order_id, rng.choice(PAY_TYPES), cents(order_cents)])
            wo.writerow([order_id, cid, status, ts.isoformat(sep=" "), ts.isoformat(sep=" ")])
            total_cents += order_cents

            # legacy (messy) copy of the order
            lemail = "" if base_of[cid] % 25 == 0 else email_for(base_of[cid])
            ldate = day.strftime(rng.choices(DATE_FMTS, DATE_W)[0])
            lstatus = rng.choice([status, status.upper(), status.title(), f" {status} "])
            lcents = order_cents
            if rng.random() < 0.005:
                lcents += rng.choice([-1, 1]) * rng.randint(100, 5000)
                stats["legacy_drifted"] += 1
            r = rng.random()
            if r < 0.01:
                lamount = ""
            elif r < 0.30:
                lamount = f"₹{lcents // 100:,}.{lcents % 100:02d}"
            else:
                lamount = cents(lcents)
            row = [order_id, lemail, ldate, lstatus, lamount]
            if rng.random() < 0.002:
                row[rng.choice([0, 2])] = rng.choice(["ABC", "31/31/2024", "N/A"])  # unparseable -> DLQ
                stats["legacy_bad_rows"] += 1
            lw.writerow(row)
            stats["legacy_rows"] += 1
            if rng.random() < 0.003:
                lw.writerow(row)
                stats["legacy_dup_rows"] += 1
        lf.close()
    for f in (fo, fi, fp):
        f.close()

    manifest = {"seed": a.seed, "customers": a.customers, "duplicate_customers": dups, "products": a.products,
                "orders": order_id, "order_items": item_id, "payments": pay_id,
                "total_payment_value": cents(total_cents), "date_range": [START.isoformat(), END.isoformat()],
                **stats}
    with open(os.path.join(a.out, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print(json.dumps(manifest, indent=2))
    return manifest


if __name__ == "__main__":
    main()
