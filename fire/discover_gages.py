"""
Discovery script: find ACTIVE USGS gages in the Tuolumne County / Rim Fire
area, rather than guessing site numbers from old inventory tables.

Context: the obvious study site - Clavey River nr Buck Meadows (11283500) -
is discontinued (record ends 1994, fire was 2013). The Rim Fire burned the
Clavey, North/Middle/South Fork Tuolumne drainages, from Jawbone to Buck
Meadows into western Yosemite. We need gages reporting both BEFORE and
AFTER August 2013 to have any pre/post comparison at all.

Discovery only - loads nothing.
"""

from __future__ import annotations

from dataretrieval import waterdata

BBOX = (-120.45, 37.70, -119.70, 38.20)  # west, south, east, north


def main() -> None:
    print("Querying USGS monitoring locations in the Rim Fire area...\n")

    try:
        sites = waterdata.get_monitoring_locations(bbox=BBOX)
    except Exception as e:
        print(f"get_monitoring_locations failed: {e}")
        print("\nAvailable functions on the module:")
        print([f for f in dir(waterdata) if not f.startswith("_")])
        return

    df = sites[0] if isinstance(sites, tuple) else sites

    if df is None or df.empty:
        print("No sites returned.")
        return

    print(f"Found {len(df)} monitoring locations")
    print(f"\nColumns available: {list(df.columns)}\n")

    type_col = next(
        (c for c in ["site_type_code", "site_type", "monitoring_location_type"]
         if c in df.columns),
        None,
    )
    if type_col:
        streams = df[df[type_col].astype(str).str.contains("ST", na=False)]
        print(f"Of those, {len(streams)} are stream sites\n")
    else:
        streams = df
        print("(couldn t identify a site-type column; showing all)\n")

    id_col = next(
        (c for c in ["monitoring_location_id", "site_no", "id"]
         if c in df.columns),
        None,
    )
    name_col = next(
        (c for c in ["monitoring_location_name", "station_nm", "name"]
         if c in df.columns),
        None,
    )

    for _, row in streams.iterrows():
        site_id = row[id_col] if id_col else "?"
        site_name = row[name_col] if name_col else "?"
        print(f"  {site_id}  {site_name}")

    print(f"\n{len(streams)} stream sites listed above.")
    print("Next: check which have discharge data spanning 2010-2016.")


if __name__ == "__main__":
    main()
