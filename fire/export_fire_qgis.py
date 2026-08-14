"""
Export burned-plot results and fire perimeters from Snowflake to
GeoPackages for QGIS.

Two layers:
  burned_plots  - the 433 before/after pairs, with biomass loss and
                  mortality change attached, positioned on the plot
  fire_perimeters - modern (2000+) perimeters, for context underneath

Perimeters come back as WKT from Snowflake and get rebuilt into real
geometry here.
"""

from __future__ import annotations

import os

import geopandas as gpd
import pandas as pd
import snowflake.connector
from shapely import wkt
from shapely.geometry import Point

SILVER = "ALPINE_WATCH.DBT_BROOKS_SILVER"
OUT_PLOTS = "C:/Users/brook/Documents/wa_burned_plots.gpkg"
OUT_FIRES = "C:/Users/brook/Documents/wa_fire_perims.gpkg"

PLOTS_Q = f"""
select
    c.plot_number,
    c.incident_name,
    c.fire_year,
    c.size_class,
    c.reported_acres,
    c.owner_group,
    c.elevation_band,
    c.pre_year,
    c.post_year,
    c.remeasure_interval,
    c.pre_live_biomass,
    c.post_live_biomass,
    c.biomass_change_tpa,
    c.pre_pct_dead,
    c.post_pct_dead,
    c.pct_dead_change,
    p.latitude,
    p.longitude
from {SILVER}.FCT_BURNED_PLOT_CHANGE c
join (
    select plot_number, max(latitude) as latitude, max(longitude) as longitude
    from {SILVER}.FCT_PLOT_TIMBER_PROFILE
    group by plot_number
) p on c.plot_number = p.plot_number
"""

FIRES_Q = f"""
select
    fire_id, incident_name, fire_year, reported_acres, size_class,
    st_asWKT(fire_geom) as geom_wkt
from {SILVER}.DIM_WA_FIRES
where fire_year >= 2000
  and reported_acres >= 1000
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

        cur.execute(PLOTS_Q)
        plots = cur.fetch_pandas_all()
        plots.columns = [c.lower() for c in plots.columns]
        print(f"burned plot pairs: {len(plots):,}")

        cur.execute(FIRES_Q)
        fires = cur.fetch_pandas_all()
        fires.columns = [c.lower() for c in fires.columns]
        print(f"fire perimeters (2000+, 1000+ ac): {len(fires):,}")
    finally:
        conn.close()

    gp = gpd.GeoDataFrame(
        plots,
        geometry=[Point(xy) for xy in zip(plots["longitude"], plots["latitude"])],
        crs="EPSG:4326",
    )
    gp.to_file(OUT_PLOTS, driver="GPKG", layer="burned_plots")
    print(f"wrote {OUT_PLOTS}")

    fires["geometry"] = fires["geom_wkt"].apply(wkt.loads)
    gf = gpd.GeoDataFrame(
        fires.drop(columns=["geom_wkt"]), geometry="geometry", crs="EPSG:4326"
    )
    gf.to_file(OUT_FIRES, driver="GPKG", layer="fire_perimeters")
    print(f"wrote {OUT_FIRES}")

    print("\nBiomass change by fire size:")
    print(
        plots.groupby("size_class")
        .agg(pairs=("plot_number", "count"),
             mean_change=("biomass_change_tpa", "mean"),
             mean_dead_chg=("pct_dead_change", "mean"))
        .round(1)
        .to_string()
    )


if __name__ == "__main__":
    main()
