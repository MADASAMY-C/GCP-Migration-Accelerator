import json
from datetime import date

import pytest

from accelerator.transforms import (normalize_email, normalize_status, parse_amount, parse_date,
                                    parse_legacy_order_line, parse_order_event)


@pytest.mark.parametrize("raw,expected", [
    ("2024-03-05", date(2024, 3, 5)), ("05/03/2024", date(2024, 3, 5)),
    ("03-05-2024", date(2024, 3, 5)), ("05 Mar 2024", date(2024, 3, 5)),
])
def test_parse_date_formats(raw, expected):
    assert parse_date(raw) == expected


@pytest.mark.parametrize("raw", ["", None, "31/31/2024", "N/A"])
def test_parse_date_rejects(raw):
    with pytest.raises(ValueError):
        parse_date(raw)


def test_parse_amount():
    assert parse_amount("₹1,234.5") == "1234.50"
    assert parse_amount("  ") is None
    assert parse_amount(None) is None
    for bad in ("abc", "-5"):
        with pytest.raises(ValueError):
            parse_amount(bad)


def test_status_and_email():
    assert normalize_status(" Delivered ") == "delivered"
    assert normalize_status("weird") == "unknown"
    assert normalize_email(" A@B.COM ") == "a@b.com"
    assert normalize_email("nope") is None


def test_legacy_line_ok_and_quoted_amount():
    r = parse_legacy_order_line('7,User7@Gmail.com,05/03/2024, SHIPPED ,"₹1,234.50"', ingest_ts="t")
    assert r["order_id"] == 7 and r["order_date"] == "2024-03-05" and r["status"] == "shipped"
    assert r["amount"] == "1234.50" and r["customer_email"] == "user7@gmail.com"


@pytest.mark.parametrize("line", ["ABC,a@b.com,2024-01-01,delivered,10", "1,a@b.com,31/31/2024,delivered,10", "1,2,3"])
def test_legacy_line_bad(line):
    with pytest.raises(ValueError):
        parse_legacy_order_line(line)


def test_event_ok():
    ev = parse_order_event(json.dumps({"event_id": "e1", "order_id": 5, "customer_id": 9,
                                       "event_type": "order_created", "amount": 10.5,
                                       "event_ts": "2024-01-01T10:00:00Z"}))
    assert ev["amount"] == "10.50" and ev["event_ts"].startswith("2024-01-01T10:00:00")


@pytest.mark.parametrize("payload", ["{not json", "[]", json.dumps({"event_id": "x"}),
                                     json.dumps({"event_id": "e", "order_id": 1, "customer_id": 1,
                                                 "event_type": "bogus", "event_ts": "2024-01-01T00:00:00Z"})])
def test_event_bad(payload):
    with pytest.raises(ValueError):
        parse_order_event(payload)
