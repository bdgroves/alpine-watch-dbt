"""
Fetch Washington wildfire perimeters from NIFC.

Target layer: InterAgencyFirePerimeterHistory - conglomerated perimeters
from USFS, BLM, BIA, FWS, NPS, CalFire and WFIGS, through the 2024 season.
That window overlaps the WA FIA record (2001-2022), which is what makes a
before/after comparison possible at all.

NIFC's ArcGIS org ID is confirmed; the exact service path is not, so this
tries several candidates and reports which responds. Paginates because the
history layer is large and ArcGIS caps records per request.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

ORG = "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services"

CANDIDATES = [
    f"{ORG}/InterAgencyFirePerimeterHistory_All_Years_View/FeatureServer/0/query",
    f"{ORG}/InterAgencyFirePerimeterHistory/FeatureServer/0/query",
    f"{ORG}/WFIGS_Interagency_Perimeters/FeatureServer/0/query",
    f"{ORG}/WFIGS_Interagency_Perimeters_YearToDate/FeatureServer/0/query",
]

BBOX = "-124.9,45.5,-116.9,49.1"   # Washington
OUT = Path("C:/Users/brook/Documents/wa_boundaries/wa_fire_perimeters.geojson")

PAGE = 1000


def try_endpoint(url: str) -> str | None:
    """Probe with a tiny request to see if the service responds at all."""
    params = {
        "where": "1=1",
        "returnCountOnly": "true",
        "f": "json",
    }
    probe = f"{url}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(probe, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if "error" in data:
            print(f"  no  ({str(data['error'])[:60]})")
            return None
        print(f"  YES - {data.get('count', '?'):,} total features nationally")
        return url
    except Exception as e:
        print(f"  no  ({str(e)[:60]})")
        return None


def fetch_page(url: str, offset: int) -> dict:
    params = {
        "geometry": BBOX,
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "outSR": "4326",
        "returnGeometry": "true",
        "resultOffset": str(offset),
        "resultRecordCount": str(PAGE),
        "f": "geojson",
    }
    full = f"{url}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(full, timeout=600) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    print("Probing NIFC endpoints:\n")
    endpoint = None
    for cand in CANDIDATES:
        print(cand.split("/services/")[1].split("/FeatureServer")[0])
        endpoint = try_endpoint(cand)
        if endpoint:
            break

    if not endpoint:
        print("\nNo endpoint responded. Need to find the current service URL.")
        return

    print(f"\nPaging Washington perimeters from that service...")
    features, offset = [], 0
    while True:
        page = fetch_page(endpoint, offset)
        if "error" in page:
            print(f"  page error: {str(page['error'])[:80]}")
            break
        got = page.get("features", [])
        features.extend(got)
        print(f"  offset {offset:>6}: +{len(got)} (total {len(features)})")
        if len(got) < PAGE:
            break
        offset += PAGE
        if offset > 30000:
            print("  stopping at 30k - unexpectedly large")
            break

    if not features:
        print("Nothing returned for the WA extent.")
        return

    props = features[0].get("properties", {})
    print(f"\nfields: {list(props.keys())}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"type": "FeatureCollection", "features": features}, fh)
    print(f"\nsaved {len(features):,} perimeters -> {OUT}")

    # Surface the largest so we can sanity-check against known WA fires
    def pick(cands):
        return next((c for c in cands if c in props), None)

    name_f = pick(["poly_IncidentName", "INCIDENT", "FIRE_NAME", "poly_Incid"])
    year_f = pick(["FIRE_YEAR", "poly_FireDiscoveryDateTime", "attr_FireDiscoveryDateTime"])
    acre_f = pick(["poly_GISAcres", "GIS_ACRES", "ACRES", "poly_Acres"])

    if name_f and acre_f:
        rows = []
        for f in features:
            p = f.get("properties", {})
            try:
                ac = float(p.get(acre_f) or 0)
            except (TypeError, ValueError):
                ac = 0
            rows.append((ac, p.get(name_f) or "?", str(p.get(year_f) or "?")[:10]))
        rows.sort(reverse=True)
        print("\nLargest WA-area perimeters:")
        for ac, nm, yr in rows[:15]:
            print(f"  {ac:>10,.0f} ac   {yr}   {nm}")


if __name__ == "__main__":
    main()
