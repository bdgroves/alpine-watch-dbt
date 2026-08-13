"""
Coverage check: which candidate gages actually have daily discharge data
spanning the Rim Fire (Aug 2013)?

A site appearing in the monitoring-locations list only means it EXISTS -
many in this basin are long discontinued. For a pre/post-fire comparison
we need continuous record on both sides of the fire.

Uses DAILY values, not 15-minute: at 15-min resolution a 2010-2016 window
is millions of rows per gage, and daily mean discharge is the standard
resolution for flashiness indices anyway.
"""

from __future__ import annotations

import time
from dataretrieval import waterdata

CANDIDATES = {
    "11278500": "Jawbone C nr Tuolumne (Jawbone Ridge - in burn)",
    "11282500": "SF Tuolumne R nr Buck Meadows (SF drainage burned)",
    "11283000": "Tuolumne R nr Buck Meadows",
    "11283500": "Clavey R nr Buck Meadows (ignition area - likely dead)",
    "11284400": "Big C ab Whites Gulch nr Groveland",
    "11284500": "Big C nr Groveland",
    "11285500": "Tuolumne R a Wards Ferry Br nr Groveland",
    "11281000": "SF Tuolumne R nr Oakland Rec Camp",
    "11282000": "M Tuolumne R a Oakland Rec Camp",
    "11276500": "Tuolumne R nr Hetch Hetchy (upstream, unburned)",
    "11284700": "NF Tuolumne R nr Long Barn",
    "11298000": "SF Stanislaus R nr Long Barn (different watershed)",
    "11296500": "SF Stanislaus R a Strawberry",
}

START = "2010-01-01"
END = "2016-12-31"


def check(site_id: str, label: str) -> None:
    try:
        result = waterdata.get_daily(
            monitoring_location_id=f"USGS-{site_id}",
            parameter_code="00060",
            time=f"{START}/{END}",
        )
    except Exception as e:
        print(f"  {site_id}  ERROR: {str(e)[:80]}")
        return

    df = result[0] if isinstance(result, tuple) else result

    if df is None or df.empty:
        print(f"  {site_id}  NO DATA          {label}")
        return

    time_col = next(
        (c for c in ["time", "date", "datetime", "value_time"] if c in df.columns),
        None,
    )
    if time_col:
        lo, hi = df[time_col].min(), df[time_col].max()
        span = f"{str(lo)[:10]} to {str(hi)[:10]}"
    else:
        span = f"(no time col; cols={list(df.columns)[:4]})"

    print(f"  {site_id}  {len(df):>5} rows   {span}   {label}")


def main() -> None:
    print(f"Checking daily discharge coverage, {START} to {END}")
    print("Rim Fire ignited 2013-08-17\n")

    for site_id, label in CANDIDATES.items():
        check(site_id, label)
        time.sleep(1.0)

    print("\nWant: sites with continuous coverage on BOTH sides of Aug 2013.")


if __name__ == "__main__":
    main()
