"""
The question that decides the whole project: is the Big Creek gage
(11284400) actually related to the Rim Fire burn?

Two checks, answering different things:
  1. Is the gage POINT inside the burn perimeter?
  2. How far is it from the perimeter edge?

Neither is the final answer. A gage can sit outside a burn while its
upstream watershed is mostly inside it (water flows downhill - the gage
measures everything above it), or sit inside a burn whose area is mostly
downstream and irrelevant. Proper answer needs watershed delineation.
This is the cheap first look.
"""

from __future__ import annotations

import geopandas as gpd
from dataretrieval import waterdata

GAGES = {
    "11284400": "Big C ab Whites Gulch nr Groveland (candidate treatment)",
    "11276500": "Tuolumne R nr Hetch Hetchy (regulated - poor control)",
    "11298000": "SF Stanislaus R nr Long Barn (candidate control)",
    "11296500": "SF Stanislaus R a Strawberry (candidate control)",
}

RIM_PATH = "C:/Users/brook/Documents/rim_fire_2013.gpkg"


def main() -> None:
    rim = gpd.read_file(RIM_PATH)
    print(f"Rim Fire polygon loaded, CRS: {rim.crs}")

    rim_utm = rim.to_crs(epsg=26910)
    rim_geom = rim_utm.geometry.iloc[0]
    print(f"Perimeter area: {rim_geom.area / 4046.86:,.0f} acres\n")

    for site_id, label in GAGES.items():
        result = waterdata.get_monitoring_locations(
            monitoring_location_id=f"USGS-{site_id}"
        )
        df = result[0] if isinstance(result, tuple) else result

        if df is None or df.empty:
            print(f"{site_id}  could not locate")
            continue

        gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
        pt = gdf.to_crs(epsg=26910).geometry.iloc[0]

        inside = rim_geom.contains(pt)
        dist_m = pt.distance(rim_geom)

        status = "INSIDE burn" if inside else f"{dist_m/1000:>6.1f} km from perimeter"
        print(f"{site_id}  {status}")
        print(f"          {label}")
        lonlat = gdf.to_crs(epsg=4326).geometry.iloc[0]
        print(f"          coords: {lonlat.y:.5f}, {lonlat.x:.5f}\n")

    print("Point-in-polygon is only a first look - the real test is what")
    print("fraction of each gage''s UPSTREAM WATERSHED burned.")


if __name__ == "__main__":
    main()
