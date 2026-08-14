"""
Export the plot timber profile from Snowflake to a GeoPackage for QGIS.

Pulls the most recent measurement per plot - FIA revisits plots, so
without this you'd map the same location several times stacked on top
of itself, and whichever point drew last would win.

Reminder on the coordinates: FIA public lat/lon is fuzzed up to ~1 mile
to protect landowner privacy. Fine for regional pattern mapping, wrong
for anything parcel-level.
"""

from __future__ import annotations

import os

import geopandas as gpd
import pandas as pd
import snowflake.connector
from shapely.geometry import Point

OUT = "C:/Users/brook/Documents/wa_timber_plots.gpkg"

QUERY = """
select
    plot_cn,
    plot_number,
    inventory_year,
    measurement_year,
    latitude,
    longitude,
    elevation_ft,
    elevation_band,
    owner_group,
    stand_age_years,
    stand_stage,
    slope_pct,
    live_trees,
    dead_trees,
    pct_dead,
    live_biomass_tons_per_acre,
    live_carbon_tons_per_acre,
    dead_biomass_tons_per_acre,
    avg_live_diameter_in,
    max_live_diameter_in,
    sawtimber_stems,
    dominant_species
from ALPINE_WATCH.DBT_BROOKS_SILVER.FCT_PLOT_TIMBER_PROFILE
qualify row_number() over (
    partition by plot_number
    order by measurement_year desc nulls last
) = 1
"""


def main() -> None:
    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
        private_key_file_pwd=os.environ["SNOWFLAKE_PRIVATE_KEY_PASSPHRASE"].encode(),
        role="TRANSFORMER",
        warehouse="ALPINE_WH",
        database="ALPINE_WATCH",
    )
    try:
        cur = conn.cursor()
        cur.execute(QUERY)
        df = cur.fetch_pandas_all()
    finally:
        conn.close()

    df.columns = [c.lower() for c in df.columns]
    print(f"fetched {len(df):,} plots (latest measurement each)")

    gdf = gpd.GeoDataFrame(
        df,
        geometry=[Point(xy) for xy in zip(df["longitude"], df["latitude"])],
        crs="EPSG:4326",
    )
    gdf.to_file(OUT, driver="GPKG", layer="timber_plots")
    print(f"wrote {OUT}")

    print("\nBy owner group:")
    print(df.groupby("owner_group").agg(
        plots=("plot_cn", "count"),
        mean_biomass=("live_biomass_tons_per_acre", "mean"),
        mean_pct_dead=("pct_dead", "mean"),
    ).round(1).to_string())


if __name__ == "__main__":
    main()
