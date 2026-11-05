from __future__ import annotations

import json

import pytest

from accelerator.transforms import (
    parse_legacy_order_line,
    parse_order_event,
)


def test_parse_legacy_ok():
    out = parse_legacy_order_line(["123", "a@b.com", "2024-01-01", "Delivered", "1234.50"])
    assert out["order_id"] == 123
    assert out["amount"] == "1234.50"
    assert out["status"] == "delivered"


def test_parse_legacy_messy():
    out = parse_legacy_order_line(["123", "", "01/02/2024", " SHIPPED ", "₹1,234.56"])
    assert out["customer_email"] is None
    assert out["order_date"] == "2024-02-01"
    assert out["amount"] == "1234.56"


@pytest.mark.parametrize("line", ["ABC,a@b.com,2024-01-01,delivered,10", "1,a@b.com,31/31/2024,delivered,10", "1,2,3"])
def test_legacy_line_bad(line):
    with pytest.raises(ValueError):
        parse_legacy_order_line(line)


def test_event_ok():
    ev = parse_order_event(json.dumps({"event_id": "e1", "order_id": 5, "customer_id": 9,
                                       "event_type": "order_created", "amount": 10.5,
                                       "event_ts": "2024-01-01T10:00:00Z"}))
    assert ev["amount"] == "10.50" and ev["event_ts"].startswith("2024-01-01T10:00:00")


def test_event_rejects_non_object_json():
    with pytest.raises(TypeError):
        parse_order_event("[]")


@pytest.mark.parametrize("payload", ["{not json", json.dumps({"event_id": "x"}),
                                     json.dumps({"event_id": "e", "order_id": 1, "customer_id": 1,
                                                 "event_type": "bogus", "event_ts": "2024-01-01T00:00:00Z"})])
def test_event_bad(payload):
    with pytest.raises(ValueError):
        parse_order_event(payload)



