"""
Bronze loader: USGS Water Quality Portal -> Snowflake.

This is the piece dbt does NOT do. dbt transforms data already in the
warehouse; something has to put it there. Pattern used here is the
standard Snowflake bulk load:

    fetch -> write NDJSON locally -> PUT to internal stage -> COPY INTO

Not row-by-row INSERTs. COPY INTO is how you load Snowflake at any
volume, and knowing the difference is an interview question.
"""

from __future__ import annotations

import gzip
import json
import os
import tempfile
import uuid
from datetime import date, timedelta
from pathlib import Path

import requests
import snowflake.connector

WQP_ENDPOINT = "https://www.waterqualitydata.us/data/Result/search"
TARGET_TABLE = "ALPINE_WATCH.BRONZE.WQP_RESULTS_RAW"


def fetch_results(station_ids: list[str], since: date) -> list[dict]:
    """Pull results for the watchlist since a given date."""
    params = {
        "siteid": station_ids,
        "startDateLo": since.strftime("%m-%d-%Y"),
        "mimeType": "json",
        "zip": "no",
    }
    response = requests.get(WQP_ENDPOINT, params=params, timeout=300)
    response.raise_for_status()
    return response.json()


def write_ndjson(records: list[dict], path: Path) -> Path:
    """One JSON object per line, gzipped. Snowflake reads this natively."""
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")
    return path


def load_to_snowflake(path: Path, batch_id: str) -> int:
    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
        role="LOADER",
        warehouse="ALPINE_WH",
        database="ALPINE_WATCH",
        schema="BRONZE",
    )

    try:
        cur = conn.cursor()

        # Idempotent DDL. VARIANT payload means schema drift upstream
        # never breaks the load - we reconcile it downstream in dbt.
        cur.execute(f"""
            create table if not exists {TARGET_TABLE} (
                payload     variant,
                _loaded_at  timestamp_ntz,
                _batch_id   varchar
            )
        """)

        # PUT into the table's own internal stage (@%TABLE).
        cur.execute(f"put file://{path} @%WQP_RESULTS_RAW auto_compress=false")

        # COPY with a transform: attach load metadata at load time so the
        # incremental watermark and batch tracing work downstream.
        cur.execute(f"""
            copy into {TARGET_TABLE} (payload, _loaded_at, _batch_id)
            from (
                select $1, current_timestamp(), '{batch_id}'
                from @%WQP_RESULTS_RAW
            )
            file_format = (type = json strip_outer_array = false)
            on_error = 'abort_statement'
            purge = true
        """)

        rows = cur.rowcount
        conn.commit()
        return rows or 0

    finally:
        conn.close()


def main() -> None:
    # Re-read a week each run. Cheap, and the dbt merge dedupes it -
    # this is what makes the pipeline replayable rather than fragile.
    since = date.today() - timedelta(days=7)
    station_ids = os.environ["ALPINE_STATION_IDS"].split(",")

    batch_id = f"{date.today().isoformat()}-{uuid.uuid4().hex[:8]}"
    records = fetch_results(station_ids, since)
    print(f"fetched {len(records)} records")

    with tempfile.TemporaryDirectory() as tmp:
        path = write_ndjson(records, Path(tmp) / "wqp.json.gz")
        loaded = load_to_snowflake(path, batch_id)

    print(f"batch {batch_id}: loaded {loaded} rows")


if __name__ == "__main__":
    main()
