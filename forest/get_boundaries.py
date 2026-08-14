"""
Fetch public-land and county boundaries for Washington, for map context.

Only the USFS endpoint below is verified. The others follow the same
ArcGIS REST conventions but are unconfirmed - so this tries each, reports
what worked, and saves whatever comes back rather than failing the whole
run on one bad URL.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

OUT_DIR = Path("C:/Users/brook/Documents/wa_boundaries")

# Washington bounding box
BBOX = "-124.9,45.5,-116.9,49.1"

SOURCES = {
    "national_forests": {
        # VERIFIED from USDA metadata
        "url": "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_ForestSystemBoundaries_01/MapServer/1/query",
        "desc": "USFS Administrative Forest Boundaries",
    },
    "wilderness": {
        "url": "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_Wilderness_01/MapServer/0/query",
        "desc": "USFS Wilderness Areas (unconfirmed endpoint)",
    },
    "counties": {
        "url": "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1/query",
        "desc": "Census TIGERweb Counties (unconfirmed endpoint)",
    },
    "national_parks": {
        "url": "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/NPS_Land_Resources_Division_Boundary_and_Tract_Data_Service/FeatureServer/2/query",
        "desc": "NPS Boundaries (unconfirmed endpoint)",
    },
}


def fetch(name: str, spec: dict) -> None:
    params = {
        "geometry": BBOX,
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "outSR": "4326",
        "returnGeometry": "true",
        "f": "geojson",
    }
    url = f"{spec['url']}?{urllib.parse.urlencode(params)}"

    print(f"\n=== {name} ===")
    print(f"  {spec['desc']}")

    try:
        with urllib.request.urlopen(url, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  FAILED: {str(e)[:90]}")
        return

    if "error" in data:
        print(f"  API error: {str(data['error'])[:90]}")
        return

    feats = data.get("features", [])
    print(f"  returned {len(feats)} features")
    if not feats:
        return

    props = feats[0].get("properties", {})
    keys = list(props.keys())[:10]
    print(f"  fields: {keys}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{name}.geojson"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    print(f"  saved -> {path}")


def main() -> None:
    print(f"Fetching WA boundary layers into {OUT_DIR}")
    for name, spec in SOURCES.items():
        fetch(name, spec)
    print("\nDone. Anything that failed can be swapped for another source.")


if __name__ == "__main__":
    main()
