from __future__ import annotations

import os

PROJECT_ID = os.environ["PROJECT_ID"]
DATASET = os.environ.get("NL2SQL_DATASET", "curated")
MODEL = os.environ.get("NL2SQL_MODEL", "gemini-1.5-pro")
MAX_BYTES = int(os.environ.get("NL2SQL_MAX_BYTES") or "1000000000")  # 1 GB scan cap
