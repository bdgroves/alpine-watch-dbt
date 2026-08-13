"""
Bronze loader: USGS continuous streamgage data -> Snowflake.

Uses dataretrieval's `waterdata` module, NOT the legacy `nwis` module.
USGS is retiring the old WaterServices API this "nwis" module is built
on - full decommission is slated for Q1 2027, with degradation possibly
starting as early as August 2026. `waterdata` is the supported path
forward, built on USGS's modernized Water Data APIs.

Unlike the WQP loader, gage identity is unambiguous - we're querying by
exact monitoring_location_id, not a bounding box. So instead of trusting
whatever column names the API returns (that guess bit us once already
on the WQP unit_code field), this script normalizes into a schema we
define ourselves before it ever reaches Snowflake. Bronze gets a clean,
self-defined contract instead of an opaque pass-through of API columns.
"""

from __future__ import annotations

import gzip
import json
import os
import tempfile
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

from dataretrieval import waterdata
import snowflake.connector

TARGET_TABLE = "ALPINE_WATCH.BRONZE.STREAMFLOW_CONTINUOUS_RAW"

# USGS parameter codes are a fixed, standardized vocabulary - safe to
# hardcode the unit each one implies, unlike WQP's free-text unit field.
PARAMETERS = {
    "00060": "cfs",    # discharge
    "00065": "ft",     # gage height
    "00010": "degC",   # water temperature
}

GAGES = [
    "11264500",  # Merced at Happy Isles - alpine anchor
    "11266500",  # Merced at Pohono Bridge - valley comparison
    "11276500",  # Tuolumne near Hetch Hetchy - alpine anchor
    "11290000",  # Tuolumne at Modesto - valley comparison
    "11298000",  # S Fork Stanislaus near Long Barn - alpine anchor
    "11303000",  # Stanislaus at Ripon - valley comparison
    "12082500",  # Nisqually near National, WA - Rainier glacial anchor
]

# Start small and provable. 15-min data over 90 days per site/parameter
# is already ~8,600 readings each - real volume without a multi-hour
# first run. Widen this once the pipeline's proven end to end.
LOOKBACK_DAYS = 90


def get_col(df, candidates: list[str]) -> str | None:
    """Same defensive pattern as fetch_lakes.py's get_col() - try each
    candidate column name in order, since the exact name returned by a
    still-new API module isn't something to assume blind."""
    for c in candidates:
        if c in df.columns:
            return c
    return None


def fetch_gage_parameter(gage_id: str, param_code: str, start: str, end: str) -> list[dict]:
    """One gage, one parameter. Normalizes into our own schema rather
    than passing through whatever the API's raw column names are."""
    try:
        df, _ = waterdata.get_continuous(
            monitoring_location_id=f"USGS-{gage_id}",
            parameter_code=param_code,
            time=f"{start}/{end}",
        )
    except Exception as e:
        print(f"    [{param_code}] ERROR: {e}")
        return []

    if df is None or df.empty:
        print(f"    [{param_code}]: 0 records")
        return []

    # Print columns once per run so the actual API shape is visible in
    # the log, not just assumed - cheap insurance against silent misses.
    if not hasattr(fetch_gage_parameter, "_logged_columns"):
        print(f"    (columns seen: {list(df.columns)})")
        fetch_gage_parameter._logged_columns = True

    time_col  = get_col(df, ["time", "datetime", "value_time", "dateTime"])
    val_col   = get_col(df, ["value", "value_double", "result"])
    qual_col  = get_col(df, ["qualifier", "approval_status", "qualifiers"])

    if not time_col or not val_col:
        print(f"    [{param_code}] WARNING: couldn't find time/value columns "
              f"in {list(df.columns)}")
        return []

    records = []
    for _, row in df.iterrows():
        try:
            val = float(row[val_col])
        except (ValueError, TypeError):
            continue
        records.append({
            "gage_id":        gage_id,
            "parameter_code": param_code,
            "unit":           PARAMETERS[param_code],
            "datetime_utc":   str(row[time_col]),
            "value":          val,
            "qualifier":      str(row[qual_col]) if qual_col else None,
        })

    print(f"    [{param_code}]: {len(records)} records")
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
        cur.execute(f"put file://{path} @%STREAMFLOW_CONTINUOUS_RAW auto_compress=false")
        cur.execute(f"""
            copy into {TARGET_TABLE} (payload, _loaded_at, _batch_id)
            from (
                select $1, current_timestamp(), '{batch_id}'
                from @%STREAMFLOW_CONTINUOUS_RAW
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
    end = date.today().isoformat()
    start = (date.today() - timedelta(days=LOOKBACK_DAYS)).isoformat()

    all_records: list[dict] = []
    for gage_id in GAGES:
        print(f"-- gage {gage_id} --")
        for param_code in PARAMETERS:
            all_records.extend(fetch_gage_parameter(gage_id, param_code, start, end))
            time.sleep(1.0)

    print(f"fetched {len(all_records)} records across {len(GAGES)} gages")

    if not all_records:
        print("nothing to load")
        return

    with tempfile.TemporaryDirectory() as tmp:
        path = write_ndjson(all_records, Path(tmp) / "streamflow.json.gz")
        loaded = load_to_snowflake(path, batch_id)

    print(f"batch {batch_id}: loaded {loaded} rows")


if __name__ == "__main__":
    main()
