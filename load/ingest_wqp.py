"""
Bronze loader: USGS Water Quality Portal -> Snowflake.

Mirrors bdgroves/Alpine-watch's fetch_lakes.py: bbox queries via
dataretrieval-python, not fixed station IDs. Two fixes baked in here
because Alpine-watch's own commit history already paid for them:
  - dataretrieval-python instead of raw REST (raw endpoint had issues)
  - startDateLo must be MM-DD-YYYY, not YYYY-MM-DD

This script's only job is getting data INTO Snowflake bronze.
Everything after that - dedup, conforming, incrementality - is dbt's job.

NOTE: LAKES below is hand-duplicated from Alpine-watch/fetch_lakes.py.
If that list changes there, update it here too. A shared config file
both repos read would remove this duplication - not done yet.
"""

from __future__ import annotations

import gzip
import json
import os
import tempfile
import time
import uuid
from datetime import date
from pathlib import Path

import dataretrieval.wqp as wqp
import snowflake.connector

TARGET_TABLE = "ALPINE_WATCH.BRONZE.WQP_RESULTS_RAW"

CHARACTERISTICS = [
    "Chlorophyll a",
    "Depth, Secchi disk depth",
    "Temperature, water",
    "Phosphorus",
]

START_DATE = "01-01-2019"  # MM-DD-YYYY - WQP silently ignores the wrong format

LAKES = [
    {"id": "lake_tahoe", "lat": 39.0968, "lon": -120.0324},
    {"id": "fallen_leaf", "lat": 38.8968, "lon": -120.0574},
    {"id": "donner_lake", "lat": 39.3196, "lon": -120.2296},
    {"id": "mono_lake", "lat": 37.9799, "lon": -119.0198},
    {"id": "convict_lake", "lat": 37.5896, "lon": -118.8577},
    {"id": "twin_lakes_bridgeport", "lat": 38.2010, "lon": -119.3510},
    {"id": "lake_chelan", "lat": 47.8418, "lon": -120.0245},
    {"id": "diablo_lake", "lat": 48.7154, "lon": -121.1376},
    {"id": "lake_cushman", "lat": 47.4685, "lon": -123.2785},
    {"id": "spirit_lake", "lat": 46.2754, "lon": -122.1413},
    {"id": "crater_lake", "lat": 42.9446, "lon": -122.1090},
    {"id": "odell_lake", "lat": 43.5568, "lon": -122.0054},
    {"id": "waldo_lake", "lat": 43.7318, "lon": -122.0454},
]


def fetch_lake(lake: dict) -> list[dict]:
    """One lake, all characteristics. A record belongs to this lake
    because THIS bbox query returned it - nothing in the record itself
    says so, which is why we tag it here, at the only point that knows."""
    lat, lon = lake["lat"], lake["lon"]
    bbox_str = f"{lon-0.05:.4f},{lat-0.05:.4f},{lon+0.05:.4f},{lat+0.05:.4f}"

    records: list[dict] = []
    for char in CHARACTERISTICS:
        try:
            df, _ = wqp.get_results(
                bBox=bbox_str,
                characteristicName=char,
                startDateLo=START_DATE,
            )
            if df is not None and not df.empty:
                for row in df.to_dict(orient="records"):
                    row["_alpine_lake_id"] = lake["id"]
                    records.append(row)
                print(f"    [{char}]: {len(df)} records")
            else:
                print(f"    [{char}]: 0 records")
        except Exception as e:
            print(f"    [{char}] ERROR: {e}")
        time.sleep(1.5)

    return records


def write_ndjson(records: list[dict], path: Path) -> Path:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, default=str) + "\n")
    return path


def load_to_snowflake(path: Path, batch_id: str) -> int:
    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
        private_key_file_pwd=os.environ["SNOWFLAKE_PRIVATE_KEY_PASSPHRASE"].encode(),
        role="TRANSFORMER",
        warehouse="ALPINE_WH",
        database="ALPINE_WATCH",
        schema="BRONZE",
    )
    try:
        cur = conn.cursor()
        cur.execute(f"""
            create table if not exists {TARGET_TABLE} (
                payload     variant,
                _loaded_at  timestamp_ntz,
                _batch_id   varchar
            )
        """)
        cur.execute(f"put file://{path} @%WQP_RESULTS_RAW auto_compress=false")
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
    batch_id = f"{date.today().isoformat()}-{uuid.uuid4().hex[:8]}"
    all_records: list[dict] = []

    for lake in LAKES:
        print(f"-- {lake['id']} --")
        all_records.extend(fetch_lake(lake))
        time.sleep(2.0)

    print(f"fetched {len(all_records)} records across {len(LAKES)} lakes")

    if not all_records:
        print("nothing to load")
        return

    with tempfile.TemporaryDirectory() as tmp:
        path = write_ndjson(all_records, Path(tmp) / "wqp.json.gz")
        loaded = load_to_snowflake(path, batch_id)

    print(f"batch {batch_id}: loaded {loaded} rows")


if __name__ == "__main__":
    main()
