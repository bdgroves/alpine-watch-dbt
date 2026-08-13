"""
Load the LiDAR-derived Nisqually stream network into Snowflake as real
GEOGRAPHY, closing the loop on the whole LiDAR side-quest: DEM ->
hydrology processing -> validated against the real gage in QGIS -> now
queryable with ST_ functions in Snowflake too.

Reprojects to EPSG:4326 before export - the source GeoPackage is in
EPSG:5070 (Albers, meters), and Snowflake''s GEOGRAPHY type assumes
WGS84 lon/lat. Casting Albers meters straight to GEOGRAPHY would silently
produce nonsense coordinates.

Only 489 rows, so this uses a simple parameterized INSERT rather than
the PUT + COPY INTO bulk pattern in the other loaders - COPY INTO earns
its setup cost at thousands of rows, not hundreds.
"""

import os

import geopandas as gpd
import snowflake.connector

GPKG_PATH = "C:/Users/brook/Documents/nisqually_streams_lines_only.gpkg"
TARGET_TABLE = "ALPINE_WATCH.BRONZE.DERIVED_STREAMS_RAW"


def main() -> None:
    gdf = gpd.read_file(GPKG_PATH)
    print(f"read {len(gdf)} features, native CRS: {gdf.crs}")

    gdf = gdf.to_crs(epsg=4326)
    print(f"reprojected to {gdf.crs}")

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
            create or replace table {TARGET_TABLE} (
                segment_id   integer,
                stream_type  varchar,
                network      integer,
                geom_wkt     varchar
            )
        """)

        rows = [
            (int(row.cat), str(row.stream_type), int(row.network), row.geometry.wkt)
            for row in gdf.itertuples()
        ]

        cur.executemany(
            f"insert into {TARGET_TABLE} (segment_id, stream_type, network, geom_wkt) "
            f"values (%s, %s, %s, %s)",
            rows,
        )
        conn.commit()
        print(f"loaded {len(rows)} rows into {TARGET_TABLE}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
