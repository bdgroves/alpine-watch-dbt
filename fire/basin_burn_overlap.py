"""
THE decisive question: what fraction of each gage''s upstream watershed
burned in the Rim Fire?

Uses USGS NLDI (Network-Linked Data Index) to fetch the authoritative,
published drainage basin for each gage rather than delineating from a DEM
ourselves. NHDPlus-derived, no derivation error of our own to defend.

Why point-in-polygon wasn''t enough, in both directions:
  - Hetch Hetchy''s gage sits INSIDE the burn, but its basin runs east into
    unburned Yosemite high country - likely a small burned fraction.
  - Big Creek''s gage sits 3.2km OUTSIDE, but its headwaters run upslope
    toward the fire - possibly a large burned fraction.
A gage measures everything that drains to it.
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
from pynhd import NLDI

GAGES = {
    "11284400": "Big C ab Whites Gulch nr Groveland",
    "11276500": "Tuolumne R nr Hetch Hetchy",
    "11298000": "SF Stanislaus R nr Long Barn",
    "11296500": "SF Stanislaus R a Strawberry",
}

RIM_PATH = "C:/Users/brook/Documents/rim_fire_2013.gpkg"
OUT_PATH = "C:/Users/brook/Documents/gage_basins.gpkg"

UTM = 26910
SQM_PER_SQMI = 2589988.11


def main() -> None:
    rim = gpd.read_file(RIM_PATH).to_crs(epsg=UTM)
    rim_geom = rim.geometry.iloc[0]
    print(f"Rim Fire: {rim_geom.area / SQM_PER_SQMI:,.1f} sq mi\n")

    nldi = NLDI()
    results = []

    for site_id, label in GAGES.items():
        try:
            basin = nldi.get_basins(site_id)
        except Exception as e:
            print(f"{site_id}  BASIN FETCH FAILED: {str(e)[:70]}")
            continue

        basin_utm = basin.to_crs(epsg=UTM)
        basin_geom = basin_utm.geometry.iloc[0]

        area_sqmi = basin_geom.area / SQM_PER_SQMI
        burned = basin_geom.intersection(rim_geom)
        burned_sqmi = burned.area / SQM_PER_SQMI
        pct = (burned_sqmi / area_sqmi * 100) if area_sqmi else 0

        print(f"{site_id}  {label}")
        print(f"          basin area:   {area_sqmi:>8,.1f} sq mi")
        print(f"          burned area:  {burned_sqmi:>8,.1f} sq mi")
        print(f"          PERCENT BURNED: {pct:>6.1f}%\n")

        basin_utm["site_id"] = site_id
        basin_utm["label"] = label
        basin_utm["area_sqmi"] = area_sqmi
        basin_utm["burned_sqmi"] = burned_sqmi
        basin_utm["pct_burned"] = pct
        results.append(basin_utm)

    if results:
        combined = gpd.GeoDataFrame(
            pd.concat(results, ignore_index=True), crs=f"EPSG:{UTM}"
        )
        combined.to_file(OUT_PATH, driver="GPKG")
        print(f"Saved basins to {OUT_PATH}")

    print("\nA usable natural experiment needs a treatment basin with a")
    print("substantial burned fraction AND controls near zero.")


if __name__ == "__main__":
    main()
