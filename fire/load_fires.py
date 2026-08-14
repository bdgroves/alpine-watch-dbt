"""
Load Washington fire perimeters into Snowflake bronze.

Bronze stays raw - all 4,921 records including the pre-modern
dendrochronology reconstructions and the duplicate agency submissions.
Filtering and deduplication happen in dbt staging, where the logic is
visible and testable rather than buried in a loader.

Geometry goes in as WKT text. The cast to GEOGRAPHY, and the validity
handling that fire perimeters always need, happen in staging too.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import geopandas as gpd
import snowflake.connector

SRC = Path("C:/Users/brook/Documents/wa_boundaries/wa_fire_perimeters.geojson")
TABLE = "ALPINE_WATCH.BRONZE.WA_FIRE_PERIMETERS_RAW"


def main() -> None:
    gdf = gpd.read_file(SRC)
    print(f"read {len(gdf):,} perimeters, CRS: {gdf.crs}")

    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
        print("reprojected to EPSG:4326")

    # Repair invalid rings before they reach Snowflake. Fire perimeters
    # are notorious for self-intersections - hand-digitized, merged from
    # multiple flights, edited across agencies.
    invalid = (~gdf.geometry.is_valid).sum()
    if invalid:
        print(f"repairing {invalid} invalid geometries")
        gdf["geometry"] = gdf.geometry.make_valid()

    rows = []
    for r in gdf.itertuples():
        def g(attr):
            v = getattr(r, attr, None)
            return None if v is None or (isinstance(v, float) and v != v) else v

        try:
            acres = float(g("GIS_ACRES") or 0)
        except (TypeError, ValueError):
            acres = None
        try:
            year = int(g("FIRE_YEAR_INT") or 0) or None
        except (TypeError, ValueError):
            year = None

        rows.append((
            str(g("OBJECTID")),
            str(g("INCIDENT") or ""),
            year,
            str(g("FIRE_YEAR") or ""),
            acres,
            str(g("AGENCY") or ""),
            str(g("SOURCE") or ""),
            str(g("FEATURE_CA") or ""),
            str(g("UNQE_FIRE_ID") or ""),
            r.geometry.wkt,
        ))

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
            create or replace table {TABLE} (
                object_id     varchar,
                incident_name varchar,
                fire_year     integer,
                fire_year_raw varchar,
                gis_acres     float,
                agency        varchar,
                source        varchar,
                feature_cat   varchar,
                unique_fire_id varchar,
                geom_wkt      varchar
            )
        """)
        cur.executemany(
            f"insert into {TABLE} (object_id, incident_name, fire_year, "
            f"fire_year_raw, gis_acres, agency, source, feature_cat, "
            f"unique_fire_id, geom_wkt) values "
            f"(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            rows,
        )
        conn.commit()

        cur.execute(f"select count(*), min(fire_year), max(fire_year) from {TABLE}")
        n, lo, hi = cur.fetchone()
        print(f"loaded {n:,} rows, fire_year range {lo} - {hi}")

        cur.execute(f"""
            select count(*) from {TABLE} where fire_year >= 2000
        """)
        print(f"  of which {cur.fetchone()[0]:,} are year 2000 or later")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
