from __future__ import annotations

import json
import os

from source_system import generate_data


def test_generate_data(tmp_path):
    manifest = generate_data.main(["--orders", "3000", "--customers", "500", "--seed", "123", "--out", str(tmp_path)])
    assert manifest["orders"] == 3000
    assert os.path.isdir(tmp_path / "oltp")
    assert os.path.isdir(tmp_path / "legacy" / "orders")
    # spot check a csv
    with open(tmp_path / "oltp" / "orders.csv", encoding="utf-8") as fh:
        lines = fh.readlines()
    assert lines[0].strip() == "order_id,customer_id,order_status,order_ts,updated_at"
    assert len(lines) == 3000 + 1
    # payments sum matches? just presence
    with open(tmp_path / "oltp" / "payments.csv", encoding="utf-8") as fh:
        rows = list(__import__("csv").DictReader(fh))
    items = {}
    with open(tmp_path / "oltp" / "order_items.csv", encoding="utf-8") as fh:
        for r in __import__("csv").DictReader(fh):
            items.setdefault(r["order_id"], 0)
            items[r["order_id"]] += int(float(r["unit_price"]) * 100) * int(r["quantity"])
    for r in rows:
        assert round(float(r["payment_value"]) * 100) == items[r["order_id"]]
    assert os.path.isdir(tmp_path / "legacy" / "orders" / "dt=2022-01-01")
    with open(tmp_path / "manifest.json", encoding="utf-8") as mf:
        assert json.load(mf)["orders"] == 3000
