"""
Fetch a DEM for the Nisqually gage area via USGS 3DEP, using py3dep -
part of the same USGS HyRiver ecosystem as dataretrieval (already used
in the streamflow loader). 3DEP's seamless national coverage already
incorporates WA DNR's own LiDAR flights, so this is the same underlying
elevation data as the state portal, just reachable through a clean API
instead of a slow map-click-download workflow.

Starts small (10m resolution, ~6km square) to prove the pipeline works
before scaling up to the full 133 sq mi watershed or native 1m LiDAR
resolution.
"""

import py3dep

GAGE_LAT, GAGE_LON = 46.7528, -122.0825
BUFFER_DEG = 0.03  # ~3km in each direction - a few km square total

bbox = (
    GAGE_LON - BUFFER_DEG,  # west
    GAGE_LAT - BUFFER_DEG,  # south
    GAGE_LON + BUFFER_DEG,  # east
    GAGE_LAT + BUFFER_DEG,  # north
)

print(f"Fetching DEM for bbox: {bbox}")
dem = py3dep.get_dem(bbox, resolution=10, crs="EPSG:4326")

out_path = "C:/Users/brook/Documents/nisqually_dem.tif"
dem.rio.to_raster(out_path)

print(f"Saved {out_path}")
print(f"CRS: {dem.rio.crs}")
print(f"Shape: {dem.shape}")
print(f"Elevation range: {float(dem.min())} to {float(dem.max())} m")
