"""Central config + SQL templating. Everything is driven by environment variables."""
import os

PROJECT_ID = os.environ.get("PROJECT_ID", "")
REGION = os.environ.get("REGION", "asia-south1")
BQ_LOCATION = os.environ.get("BQ_LOCATION", REGION)
PRICE_PER_TB_USD = float(os.environ.get("BQ_PRICE_PER_TB_USD", "6.25"))  # check current on-demand pricing


def render(sql: str, **extra: str) -> str:
    """Replace ${PROJECT_ID}, ${REGION} (and any extras) in SQL text."""
    values = {"PROJECT_ID": PROJECT_ID, "REGION": REGION, **extra}
    for key, val in values.items():
        sql = sql.replace("${" + key + "}", str(val))
    return sql
