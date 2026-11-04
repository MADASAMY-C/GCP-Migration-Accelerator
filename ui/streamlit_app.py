import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from accelerator.data_upload import DataUploadNormalizer

st.set_page_config(page_title="GCP Migration Accelerator - Data Upload", layout="wide")

st.title("GCP Migration Accelerator - Upload Real Data")
st.markdown("Upload your own CSV/Excel files and convert them to match the pipeline schemas. Skip the synthetic data generator.")

normalizer = DataUploadNormalizer(out_dir="data")

tab1, tab2, tab3, tab4 = st.tabs(["1) Upload Files", "2) Map Columns", "3) Normalize & Preview", "4) Load & Export"])

with tab1:
    st.header("Upload your source files")
    st.info("You can upload any combination. At minimum, you need orders data. For full OLTP + CDC flow, upload all tables.")
    col1, col2 = st.columns(2)
    with col1:
        customers_file = st.file_uploader("Customers (CSV/Excel/JSON)", type=["csv", "xlsx", "xls", "json"])
        products_file = st.file_uploader("Products (CSV/Excel/JSON)", type=["csv", "xlsx", "xls", "json"])
        orders_file = st.file_uploader("Orders (CSV/Excel/JSON)", type=["csv", "xlsx", "xls", "json"])
    with col2:
        order_items_file = st.file_uploader("Order Items (CSV/Excel/JSON)", type=["csv", "xlsx", "xls", "json"])
        payments_file = st.file_uploader("Payments (CSV/Excel/JSON)", type=["csv", "xlsx", "xls", "json"])

    def load_file(f):
        if f is None:
            return None
        try:
            name = f.name.lower()
            if name.endswith(".csv"):
                return pd.read_csv(f)
            if name.endswith((".xlsx", ".xls")):
                return pd.read_excel(f)
            if name.endswith(".json"):
                return pd.read_json(f)
            return pd.read_csv(f)
        except (OSError, pd.errors.ParserError, ValueError) as e:
            st.error(f"Error loading {getattr(f, 'name', 'file')}: {e}")
            return None

    st.session_state["customers"] = load_file(customers_file)
    st.session_state["products"] = load_file(products_file)
    st.session_state["orders"] = load_file(orders_file)
    st.session_state["order_items"] = load_file(order_items_file)
    st.session_state["payments"] = load_file(payments_file)

    for k in ["customers", "products", "orders", "order_items", "payments"]:
        df = st.session_state.get(k)
        if df is not None and isinstance(df, pd.DataFrame) and not df.empty:
            st.success(f"Loaded {k}: {len(df)} rows")

with tab2:
    st.header("Map your columns to expected schema")
    st.caption("Map your file columns to the expected pipeline columns.")
    expected = {
        "customers": ["customer_id", "full_name", "email", "phone", "city", "state", "created_at"],
        "products": ["product_id", "product_name", "category", "price"],
        "orders": ["order_id", "customer_id", "order_status", "order_ts", "updated_at"],
        "order_items": ["order_item_id", "order_id", "product_id", "quantity", "unit_price"],
        "payments": ["payment_id", "order_id", "payment_type", "payment_value"],
    }
    column_maps = {}
    for tbl, exp_cols in expected.items():
        df = st.session_state.get(tbl)
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            continue
        st.subheader(f"{tbl} ({len(df)} rows)")
        cols = list(df.columns)
        col_map = {}
        for exp in exp_cols:
            sel = st.selectbox(f"Map to {exp}", ["(ignore)"] + cols, key=f"map_{tbl}_{exp}")
            if sel != "(ignore)":
                col_map[sel] = exp
        column_maps[tbl] = col_map
        if col_map:
            st.write(col_map)
    st.session_state["column_maps"] = column_maps

with tab3:
    st.header("Normalize and preview")
    if st.button("Normalize data"):
        orders_df = st.session_state.get("orders")
        if orders_df is None or not isinstance(orders_df, pd.DataFrame) or orders_df.empty:
            st.error("You must upload and have at least 'Orders' data to normalize.")
        else:
            try:
                oltp = normalizer.normalize_oltp(
                    customers=st.session_state.get("customers"),
                    products=st.session_state.get("products"),
                    orders=orders_df,
                    order_items=st.session_state.get("order_items"),
                    payments=st.session_state.get("payments"),
                    column_maps=st.session_state.get("column_maps", {}) or {},
                )
                legacy = normalizer.normalize_legacy_from_orders(
                    orders=orders_df,
                    customers=st.session_state.get("customers"),
                    column_maps=st.session_state.get("column_maps", {}) or {},
                )
                st.session_state["oltp_norm"] = oltp
                st.session_state["legacy_norm"] = legacy
                st.success("Normalized successfully!")
            except (ValueError, KeyError, TypeError) as e:
                st.error(f"Error: {e}")

    if st.session_state.get("oltp_norm"):
        st.subheader("OLTP Preview")
        for k, df in st.session_state["oltp_norm"].items():
            with st.expander(f"{k} ({len(df)} rows)"):
                st.dataframe(df.head(10))

    if st.session_state.get("legacy_norm") is not None:
        st.subheader("Legacy (Hive-style) Preview")
        st.dataframe(st.session_state["legacy_norm"].head(20))
        st.caption(f"{len(st.session_state['legacy_norm'])} rows")

with tab4:
    st.header("Write files & load")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Write to data/ (OLTP + Legacy)"):
            try:
                written = []
                if st.session_state.get("oltp_norm"):
                    written += normalizer.write_oltp(st.session_state["oltp_norm"])
                if st.session_state.get("legacy_norm") is not None:
                    written += normalizer.write_legacy_partitioned(st.session_state["legacy_norm"])
                mpath = normalizer.write_manifest(st.session_state.get("oltp_norm", {}) or {}, st.session_state.get("legacy_norm"))
                written.append(mpath)
                st.success(f"Wrote {len(written)} files")
                for w in written:
                    st.code(w)
            except (OSError, ValueError) as e:
                st.error(f"Error: {e}")

    with col2:
        st.subheader("Next steps")
        st.markdown("""
        **Local Postgres (if Docker available):**
        ```bash
        docker compose -f source_system/docker-compose.yml up -d
        bash source_system/load_postgres.sh data
        ```

        **Upload legacy to GCS:**
        ```bash
        gsutil -m cp -r data/legacy/orders gs://$PROJECT_ID-$PREFIX-legacy/
        ```
        """)
