"""
Fetch fire perimeters for the Tuolumne County area from CAL FIRE FRAP''s
authoritative historical dataset (1878-present), via ArcGIS REST.

Why this source and not MTBS: MTBS''s direct-download page is a JS app
with no stable file URL to script against. CAL FIRE FRAP is the
authoritative CA perimeter dataset, queryable over a documented REST
endpoint, and it''s the same lineage BdgrovesBot already uses for the
Wikipedia wildfire infoboxes.

Tradeoff: FRAP gives perimeters but NOT burn severity. MTBS adds
dNBR-derived severity classes, which would let us weight a watershed by
how hard it burned rather than just whether it burned. Worth adding later
if the simple version shows signal.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

SERVICE = (
    "https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/"
    "California_Historic_Fire_Perimeters/FeatureServer/0/query"
)

BBOX = (-120.45, 37.70, -119.70, 38.20)  # west, south, east, north

OUT_PATH = "C:/Users/brook/Documents/tuolumne_fire_perimeters.geojson"


def build_url() -> str:
    params = {
        "geometry": ",".join(str(c) for c in BBOX),
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "outSR": "4326",
        "returnGeometry": "true",
        "f": "geojson",
    }
    return f"{SERVICE}?{urllib.parse.urlencode(params)}"


def main() -> None:
    url = build_url()
    print(f"Querying CAL FIRE FRAP for fires intersecting {BBOX}\n")

    with urllib.request.urlopen(url, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if "error" in data:
        print(f"API returned an error: {data['error']}")
        return

    features = data.get("features", [])
    print(f"Returned {len(features)} fire perimeters")

    if not features:
        print("Nothing came back - check the bbox or field names.")
        return

    props = features[0].get("properties", {})
    print(f"\nField names: {list(props.keys())}\n")

    def pick(candidates):
        return next((c for c in candidates if c in props), None)

    name_f = pick(["FIRE_NAME", "fire_name", "NAME"])
    year_f = pick(["YEAR_", "YEAR", "year_", "FIRE_YEAR"])
    acre_f = pick(["GIS_ACRES", "gis_acres", "ACRES"])

    rows = []
    for f in features:
        p = f.get("properties", {})
        rows.append((
            p.get(acre_f) or 0,
            p.get(name_f) or "?",
            p.get(year_f) or "?",
        ))

    rows.sort(reverse=True)
    print("Largest fires in this extent:")
    for acres, name, year in rows[:15]:
        try:
            acres_s = f"{float(acres):>10,.0f}"
        except (TypeError, ValueError):
            acres_s = f"{acres:>10}"
        print(f"  {acres_s} ac   {year}   {name}")

    rim = [r for r in rows if str(r[1]).upper() == "RIM"]
    print(f"\nRim Fire records found: {len(rim)}")
    for acres, name, year in rim:
        print(f"  {name} ({year}): {float(acres):,.0f} acres")

    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    print(f"\nSaved {OUT_PATH}")


if __name__ == "__main__":
    main()
