"""Data upload normalizer to convert real CSV/Excel files to pipeline schemas."""
from __future__ import annotations

import json
import os
import re
from datetime import UTC, date, datetime
from typing import Any

import pandas as pd


class DataUploadNormalizer:
    def __init__(self, out_dir: str = "data"):
        self.out_dir = out_dir
        self.oltp_dir = os.path.join(out_dir, "oltp")
        self.legacy_root = os.path.join(out_dir, "legacy", "orders")
        os.makedirs(self.oltp_dir, exist_ok=True)
        os.makedirs(self.legacy_root, exist_ok=True)

    @staticmethod
    def _deduplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or not isinstance(df, pd.DataFrame):
            return df
        if df.columns.duplicated().any():
            df = df.loc[:, ~df.columns.duplicated()]
        return df

    @staticmethod
    def _clean_amount(val: Any) -> float | None:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        s = str(val).strip()
        if s == "" or s.lower() in {"nan", "null", "none"}:
            return None
        s = re.sub(r"[^\d\.\-]", "", s)
        if s == "" or s == "-":
            return None
        try:
            return float(s)
        except ValueError:
            return None

    @staticmethod
    def _parse_date(val: Any):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        if isinstance(val, (datetime, pd.Timestamp)):
            return val.date()
        if isinstance(val, date):
            return val
        s = str(val).strip()
        if not s:
            return None
        for fmt in (
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%m-%d-%Y",
            "%m/%d/%Y",
            "%d %b %Y",
            "%d-%b-%Y",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                s_clean = s.split("T")[0].split(" ")[0]
                return datetime.strptime(s_clean, fmt).date()
            except ValueError:
                continue
        try:
            return pd.to_datetime(s).date()
        except (ValueError, TypeError):
            return None

    def normalize_oltp(
        self,
        customers: pd.DataFrame | None = None,
        products: pd.DataFrame | None = None,
        orders: pd.DataFrame | None = None,
        order_items: pd.DataFrame | None = None,
        payments: pd.DataFrame | None = None,
        column_maps: dict[str, dict[str, str]] | None = None,
    ) -> dict[str, pd.DataFrame]:
        maps = column_maps or {}
        out: dict[str, pd.DataFrame] = {}

        if customers is not None and isinstance(customers, pd.DataFrame) and not customers.empty:
            df = customers.copy()
            df = self._deduplicate_columns(df)
            m = maps.get("customers", {}) or {}
            df = df.rename(columns={k: v for k, v in m.items() if k in df.columns})
            df = self._deduplicate_columns(df)
            for col in ["customer_id", "full_name", "email", "phone", "city", "state", "created_at"]:
                if col not in df.columns:
                    df[col] = None
            df["created_at"] = df["created_at"].apply(lambda x: self._parse_date(x) or date(2023, 1, 1))
            df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
            df = self._deduplicate_columns(df)
            out["customers"] = df[["customer_id", "full_name", "email", "phone", "city", "state", "created_at"]]

        if products is not None and isinstance(products, pd.DataFrame) and not products.empty:
            df = products.copy()
            df = self._deduplicate_columns(df)
            m = maps.get("products", {}) or {}
            df = df.rename(columns={k: v for k, v in m.items() if k in df.columns})
            df = self._deduplicate_columns(df)
            for col in ["product_id", "product_name", "category", "price"]:
                if col not in df.columns:
                    df[col] = None
            df["price"] = df["price"].apply(self._clean_amount)
            df = self._deduplicate_columns(df)
            out["products"] = df[["product_id", "product_name", "category", "price"]]

        if orders is not None and isinstance(orders, pd.DataFrame) and not orders.empty:
            df = orders.copy()
            df = self._deduplicate_columns(df)
            m = maps.get("orders", {}) or {}
            df = df.rename(columns={k: v for k, v in m.items() if k in df.columns})
            df = self._deduplicate_columns(df)
            for col in ["order_id", "customer_id", "order_status", "order_ts", "updated_at"]:
                if col not in df.columns:
                    df[col] = None
            df["order_ts"] = df["order_ts"].apply(lambda x: self._parse_date(x) or date(2023, 1, 1))
            first_ts = df["order_ts"].iloc[0] if len(df) else date(2023, 1, 1)
            df["updated_at"] = df["updated_at"].apply(lambda x: self._parse_date(x) or first_ts)
            df["order_ts"] = pd.to_datetime(df["order_ts"]).dt.strftime("%Y-%m-%d %H:%M:%S")
            df["updated_at"] = pd.to_datetime(df["updated_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
            df = self._deduplicate_columns(df)
            out["orders"] = df[["order_id", "customer_id", "order_status", "order_ts", "updated_at"]]

        if order_items is not None and isinstance(order_items, pd.DataFrame) and not order_items.empty:
            df = order_items.copy()
            df = self._deduplicate_columns(df)
            m = maps.get("order_items", {}) or {}
            df = df.rename(columns={k: v for k, v in m.items() if k in df.columns})
            df = self._deduplicate_columns(df)
            for col in ["order_item_id", "order_id", "product_id", "quantity", "unit_price"]:
                if col not in df.columns:
                    df[col] = None
            df["unit_price"] = df["unit_price"].apply(self._clean_amount)
            df = self._deduplicate_columns(df)
            out["order_items"] = df[["order_item_id", "order_id", "product_id", "quantity", "unit_price"]]

        if payments is not None and isinstance(payments, pd.DataFrame) and not payments.empty:
            df = payments.copy()
            df = self._deduplicate_columns(df)
            m = maps.get("payments", {}) or {}
            df = df.rename(columns={k: v for k, v in m.items() if k in df.columns})
            df = self._deduplicate_columns(df)
            for col in ["payment_id", "order_id", "payment_type", "payment_value"]:
                if col not in df.columns:
                    df[col] = None
            df["payment_value"] = df["payment_value"].apply(self._clean_amount)
            df = self._deduplicate_columns(df)
            out["payments"] = df[["payment_id", "order_id", "payment_type", "payment_value"]]

        return out

    def normalize_legacy_from_orders(
        self, orders: pd.DataFrame, customers: pd.DataFrame | None = None, column_maps: dict[str, dict[str, str]] | None = None
    ) -> pd.DataFrame:
        if orders is None or not isinstance(orders, pd.DataFrame) or orders.empty:
            msg = "Orders data is required to generate legacy files"
            raise ValueError(msg)
        maps = column_maps or {}
        df = orders.copy()
        df = self._deduplicate_columns(df)
        m = maps.get("orders", {}) or {}
        df = df.rename(columns={k: v for k, v in m.items() if k in df.columns})
        df = self._deduplicate_columns(df)
        if "order_date" not in df.columns and "order_ts" in df.columns:
            df["order_date"] = df["order_ts"].apply(self._parse_date)
        elif "order_date" in df.columns:
            df["order_date"] = df["order_date"].apply(self._parse_date)
        else:
            df["order_date"] = date(2023, 1, 1)
        if "status" not in df.columns and "order_status" in df.columns:
            df["status"] = df["order_status"]
        if "amount" not in df.columns:
            df["amount"] = None
        if "customer_email" not in df.columns:
            if customers is not None and isinstance(customers, pd.DataFrame) and not customers.empty and "customer_id" in df.columns and "email" in customers.columns:
                c = customers.copy()
                c = self._deduplicate_columns(c)
                cm = maps.get("customers", {}) or {}
                c = c.rename(columns={k: v for k, v in cm.items() if k in c.columns})
                c = self._deduplicate_columns(c)
                try:
                    df = df.merge(c[["customer_id", "email"]].rename(columns={"email": "customer_email"}), on="customer_id", how="left")
                except (KeyError, ValueError):
                    df["customer_email"] = None
            else:
                df["customer_email"] = None
        df = self._deduplicate_columns(df)
        legacy = pd.DataFrame(
            {
                "order_id": df.get("order_id"),
                "customer_email": df.get("customer_email"),
                "order_date": df["order_date"].apply(
                    lambda x: x.strftime("%Y-%m-%d") if hasattr(x, "strftime") and x is not None else (str(x) if x is not None else "2023-01-01")
                ),
                "status": df.get("status"),
                "amount": df.get("amount").apply(self._clean_amount) if "amount" in df.columns else None,
            }
        )
        return legacy

    def write_oltp(self, oltp: dict[str, pd.DataFrame]) -> list[str]:
        written: list[str] = []
        if not oltp:
            return written
        for name, df in oltp.items():
            if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                continue
            df = self._deduplicate_columns(df)
            path = os.path.join(self.oltp_dir, f"{name}.csv")
            df.to_csv(path, index=False)
            written.append(path)
        return written

    def write_legacy_partitioned(self, legacy: pd.DataFrame) -> list[str]:
        written: list[str] = []
        if legacy is None or not isinstance(legacy, pd.DataFrame) or legacy.empty:
            return written
        df = legacy.copy()
        df = self._deduplicate_columns(df)
        df["order_date_parsed"] = df["order_date"].apply(lambda x: self._parse_date(x))
        df = df.dropna(subset=["order_date_parsed"])
        if df.empty:
            return written
        for d, g in df.groupby("order_date_parsed"):
            part_dir = os.path.join(self.legacy_root, f"dt={d.isoformat()}")
            os.makedirs(part_dir, exist_ok=True)
            path = os.path.join(part_dir, "part-0000.csv")
            out = g[["order_id", "customer_email", "order_date_parsed", "status", "amount"]].copy()
            out = self._deduplicate_columns(out)
            out = out.rename(columns={"order_date_parsed": "order_date"})
            out["order_date"] = out["order_date"].apply(lambda x: x.strftime("%Y-%m-%d"))
            out.to_csv(path, index=False)
            written.append(path)
        return written

    def write_manifest(self, oltp: dict[str, pd.DataFrame], legacy: pd.DataFrame) -> str:
        manifest = {
            "source": "user_upload",
            "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "orders": len(legacy) if legacy is not None and isinstance(legacy, pd.DataFrame) else (len(oltp.get("orders", [])) if oltp and "orders" in oltp else 0),
            "customers": len(oltp.get("customers", [])) if oltp and "customers" in oltp else None,
            "products": len(oltp.get("products", [])) if oltp and "products" in oltp else None,
            "order_items": len(oltp.get("order_items", [])) if oltp and "order_items" in oltp else None,
            "payments": len(oltp.get("payments", [])) if oltp and "payments" in oltp else None,
        }
        path = os.path.join(self.out_dir, "manifest.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)
        return path
