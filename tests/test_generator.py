import csv
import json
import os

from source_system.generate_data import main


def test_small_generation(tmp_path):
    m = main(["--orders", "3000", "--customers", "500", "--products", "50", "--out", str(tmp_path)])
    assert m["orders"] == 3000 and m["payments"] == 3000 and m["order_items"] >= 3000
    with open(tmp_path / "oltp" / "orders.csv", encoding="utf-8") as fh:
        assert sum(1 for _ in csv.reader(fh)) == 3001
    # payments must equal the sum of items per order (so source totals are internally consistent)
    items = {}
    with open(tmp_path / "oltp" / "order_items.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            items[r["order_id"]] = items.get(r["order_id"], 0) + round(float(r["unit_price"]) * 100) * int(r["quantity"])
    with open(tmp_path / "oltp" / "payments.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            assert round(float(r["payment_value"]) * 100) == items[r["order_id"]]
    assert os.path.isdir(tmp_path / "legacy" / "orders" / "dt=2022-01-01")
    assert json.load(open(tmp_path / "manifest.json"))["orders"] == 3000
