"""
Load the Sierra hydrology sandbox into Snowflake bronze.

Two tables, deliberately different shapes so there's something to practice
on in both directions:

  SIERRA_GAGES_RAW      14 rows.  Gage metadata + NLDI basin polygon as WKT.
                        Static reference - create-or-replace, simple INSERT.

  SIERRA_DAILY_FLOW_RAW ~163K rows. Daily mean discharge, 1990-2026.
                        Bulk load via stage + COPY INTO.

The contrast is the point: 14 rows doesn't earn COPY INTO's setup cost,
163K does. Same reasoning as the other loaders in this repo.
"""

from __future__ import annotations

import csv
import gzip
import json
import os
import tempfile
import time
import uuid
from datetime import date
from pathlib import Path

import geopandas as gpd
import snowflake.connector
from dataretrieval import waterdata
from pynhd import NLDI

SEED_CSV = "C:/Users/brook/Documents/alpine-watch-dbt/seeds/sierra_gages.csv"
GAGES_TABLE = "ALPINE_WATCH.BRONZE.SIERRA_GAGES_RAW"
FLOW_TABLE = "ALPINE_WATCH.BRONZE.SIERRA_DAILY_FLOW_RAW"

START = "1990-01-01"
END = "2026-08-13"


def connect():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
        private_key_file_pwd=os.environ["SNOWFLAKE_PRIVATE_KEY_PASSPHRASE"].encode(),
        role="TRANSFORMER",
        warehouse="ALPINE_WH",
        database="ALPINE_WATCH",
        schema="BRONZE",
    )


def read_gage_ids() -> list[str]:
    with open(SEED_CSV, newline="", encoding="utf-8") as fh:
        return [row["gage_id"] for row in csv.DictReader(fh)]


def fetch_gage_metadata(gage_ids: list[str]) -> list[tuple]:
    """Gage attributes + NLDI basin polygon, in WGS84 for Snowflake GEOGRAPHY."""
    rows = []
    for gid in gage_ids:
        name = lat = lon = None
        drainage = None
        try:
            res = waterdata.get_monitoring_locations(
                monitoring_location_id=f"USGS-{gid}"
            )
            df = res[0] if isinstance(res, tuple) else res
            if df is not None and not df.empty:
                r = df.iloc[0]
                name = str(r.get("monitoring_location_name", ""))
                drainage = r.get("drainage_area")
                geom = df.geometry.iloc[0]
                lat, lon = geom.y, geom.x
        except Exception as e:
            print(f"  {gid} metadata failed: {str(e)[:50]}")

        basin_wkt = None
        try:
            basin = NLDI().get_basins(gid).to_crs(epsg=4326)
            basin_wkt = basin.geometry.iloc[0].wkt
        except Exception as e:
            print(f"  {gid} basin failed: {str(e)[:50]}")

        try:
            drainage = float(drainage) if drainage is not None else None
        except (TypeError, ValueError):
            drainage = None

        rows.append((gid, name, lat, lon, drainage, basin_wkt))
        print(f"  {gid}  {name[:45]:<45} basin={'yes' if basin_wkt else 'NO'}")
        time.sleep(0.5)
    return rows


def load_gages(cur, rows: list[tuple]) -> None:
    cur.execute(f"""
        create or replace table {GAGES_TABLE} (
            gage_id        varchar,
            gage_name      varchar,
            latitude       float,
            longitude      float,
            drainage_area  float,
            basin_wkt      varchar
        )
    """)
    cur.executemany(
        f"insert into {GAGES_TABLE} "
        f"(gage_id, gage_name, latitude, longitude, drainage_area, basin_wkt) "
        f"values (%s, %s, %s, %s, %s, %s)",
        rows,
    )
    print(f"loaded {len(rows)} gages")


def fetch_daily(gage_ids: list[str]) -> list[dict]:
    records = []
    for gid in gage_ids:
        try:
            res = waterdata.get_daily(
                monitoring_location_id=f"USGS-{gid}",
                parameter_code="00060",
                time=f"{START}/{END}",
            )
        except Exception as e:
            print(f"  {gid} ERROR {str(e)[:50]}")
            continue

        df = res[0] if isinstance(res, tuple) else res
        if df is None or df.empty:
            print(f"  {gid} no data")
            continue

        tcol = next((c for c in ["time", "date", "datetime"] if c in df.columns), None)
        vcol = next((c for c in ["value", "value_double"] if c in df.columns), None)
        qcol = next((c for c in ["approval_status", "qualifier"] if c in df.columns), None)

        if not tcol or not vcol:
            print(f"  {gid} unexpected columns: {list(df.columns)[:6]}")
            continue

        n = 0
        for _, row in df.iterrows():
            try:
                val = float(row[vcol])
            except (TypeError, ValueError):
                continue
            records.append({
                "gage_id": gid,
                "flow_date": str(row[tcol])[:10],
                "discharge_cfs": val,
                "approval": str(row[qcol]) if qcol else None,
            })
            n += 1
        print(f"  {gid}  {n:>6,} daily values")
        time.sleep(0.8)
    return records


def load_daily(cur, records: list[dict], batch_id: str) -> None:
    cur.execute(f"""
        create or replace table {FLOW_TABLE} (
            payload     variant,
            _loaded_at  timestamp_ntz,
            _batch_id   varchar
        )
    """)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "daily.json.gz"
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec, default=str) + "\n")

        cur.execute(f"put file://{path} @%SIERRA_DAILY_FLOW_RAW auto_compress=false")
        cur.execute(f"""
            copy into {FLOW_TABLE} (payload, _loaded_at, _batch_id)
            from (
                select $1, current_timestamp(), '{batch_id}'
                from @%SIERRA_DAILY_FLOW_RAW
            )
            file_format = (type = json strip_outer_array = false)
            on_error = 'abort_statement'
            purge = true
        """)
    print(f"staged {len(records):,} daily records")


def main() -> None:
    gage_ids = read_gage_ids()
    batch_id = f"{date.today().isoformat()}-{uuid.uuid4().hex[:8]}"
    print(f"Sandbox load: {len(gage_ids)} gages, batch {batch_id}\n")

    print("-- gage metadata + basins --")
    gage_rows = fetch_gage_metadata(gage_ids)

    print("\n-- daily discharge --")
    daily = fetch_daily(gage_ids)
    print(f"\nfetched {len(daily):,} daily records total")

    conn = connect()
    try:
        cur = conn.cursor()
        load_gages(cur, gage_rows)
        if daily:
            load_daily(cur, daily, batch_id)
        conn.commit()
    finally:
        conn.close()

    print("\nDone. Bronze tables ready for dbt.")


if __name__ == "__main__":
    main()
