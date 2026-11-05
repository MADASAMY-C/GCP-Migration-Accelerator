"""Pure-Python parsing / validation logic shared by the Beam pipelines (and unit-tested without Beam)."""
from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m-%d-%Y", "%d %b %Y")
KNOWN_STATUSES = {"delivered", "shipped", "processing", "canceled", "returned"}
EVENT_TYPES = {"order_created", "payment_captured", "order_shipped", "order_canceled"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

LEGACY_SCHEMA = (
    "order_id:INTEGER,customer_email:STRING,order_date:DATE,status:STRING,"
    "amount:NUMERIC,source_order_date:STRING,ingest_ts:TIMESTAMP"
)
LEGACY_DLQ_SCHEMA = "raw_line:STRING,error:STRING,ingest_ts:TIMESTAMP"
EVENT_SCHEMA = (
    "event_id:STRING,order_id:INTEGER,customer_id:INTEGER,event_type:STRING,"
    "amount:NUMERIC,event_ts:TIMESTAMP,ingest_ts:TIMESTAMP"
)
AGG_SCHEMA = "window_start:TIMESTAMP,window_end:TIMESTAMP,event_type:STRING,event_count:INTEGER,amount_sum:NUMERIC"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_date(value: str | None):
    if value is None or not value.strip():
        raise ValueError("missing order_date")
    s = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unparseable order_date: {value!r}")


def parse_amount(value: str | None) -> str | None:
    """'₹1,234.5' -> '1234.50'; blank -> None; garbage / negative -> ValueError."""
    if value is None or not value.strip():
        return None
    cleaned = re.sub(r"[₹$\s,]", "", value)
    try:
        amt = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"bad amount: {value!r}") from exc
    if amt < 0 or not amt.is_finite():
        raise ValueError(f"negative or non-finite amount: {value!r}")
    return str(amt.quantize(Decimal("0.01")))


def normalize_status(value: str | None) -> str:
    s = (value or "").strip().lower()
    return s if s in KNOWN_STATUSES else "unknown"


def normalize_email(value: str | None) -> str | None:
    s = (value or "").strip().lower()
    return s if EMAIL_RE.match(s) else None


def parse_legacy_order_line(line: str | list[str] | tuple[str, ...], ingest_ts: str | None = None) -> dict:
    """Parse one line of the legacy Hive-export CSV. Raises ValueError for rows that belong in the DLQ."""
    if isinstance(line, (list, tuple)):
        row = list(line)
    else:
        row = next(csv.reader([line]), [])
    if len(row) != 5:
        raise ValueError(f"expected 5 columns, got {len(row)}")
    order_id_raw, email, order_date, status, amount = row
    try:
        order_id = int(order_id_raw.strip())
    except ValueError as exc:
        raise ValueError(f"bad order_id: {order_id_raw!r}") from exc
    return {
        "order_id": order_id,
        "customer_email": normalize_email(email),
        "order_date": parse_date(order_date).isoformat(),
        "status": normalize_status(status),
        "amount": parse_amount(amount),
        "source_order_date": order_date,
        "ingest_ts": ingest_ts or utcnow_iso(),
    }


def parse_order_event(payload: bytes | str, ingest_ts: str | None = None) -> dict:
    """Parse a Pub/Sub order-event JSON message. Raises ValueError for DLQ-bound messages."""
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    try:
        obj = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid json: {exc}") from exc
    if not isinstance(obj, dict):
        raise TypeError("event must be a JSON object")
    for field in ("event_id", "order_id", "customer_id", "event_type", "event_ts"):
        if obj.get(field) in (None, ""):
            raise ValueError(f"missing field: {field}")
    if obj["event_type"] not in EVENT_TYPES:
        raise ValueError(f"unknown event_type: {obj['event_type']!r}")
    try:
        ts = datetime.fromisoformat(str(obj["event_ts"]).replace("Z", "+00:00"))
        order_id, customer_id = int(obj["order_id"]), int(obj["customer_id"])
    except (ValueError, TypeError) as exc:
        raise ValueError(f"bad field value: {exc}") from exc
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    ts = ts.astimezone(timezone.utc)
    amount = parse_amount(str(obj["amount"])) if obj.get("amount") is not None else None
    return {
        "event_id": str(obj["event_id"]),
        "order_id": order_id,
        "customer_id": customer_id,
        "event_type": obj["event_type"],
        "amount": amount,
        "event_ts": ts.isoformat(),
        "event_epoch": ts.timestamp(),
        "ingest_ts": ingest_ts or utcnow_iso(),
    }
