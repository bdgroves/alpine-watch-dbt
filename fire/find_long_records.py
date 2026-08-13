"""
Find Sierra gages with LONG daily discharge records, to build a hydrology
sandbox worth practicing on.

Not looking for a natural experiment anymore - looking for data with good
structure: decades of daily values (window functions, rolling stats,
water-year aggregation), spread across a few watersheds (spatial joins),
at a volume where query performance is actually observable.

Writes the keepers to a CSV that becomes a dbt seed.
"""

from __future__ import annotations

import csv
import time

from dataretrieval import waterdata

CANDIDATES = [
    "11266500", "11268400", "11269300",
    "11274800", "11275000", "11276500", "11276600", "11276900",
    "11277000", "11277300", "11278000", "11278300", "11278500",
    "11279500", "11280000", "11281000", "11281500", "11282000",
    "11282500", "11283000", "11283100", "11283200", "11283250",
    "11283300", "11283350", "11283500", "11284400", "11284500",
    "11284700", "11284800", "11285000", "11285200", "11285500",
    "11286000", "11286500", "11288000",
    "11292900", "11293000", "11295400", "11295910", "11296500",
    "11297200", "11298000", "11298600",
]

START = "1990-01-01"
END = "2026-08-13"
MIN_ROWS = 3650

OUT_CSV = "C:/Users/brook/Documents/alpine-watch-dbt/seeds/sierra_gages.csv"


def probe(site_id: str) -> dict | None:
    try:
        result = waterdata.get_daily(
            monitoring_location_id=f"USGS-{site_id}",
            parameter_code="00060",
            time=f"{START}/{END}",
        )
    except Exception as e:
        print(f"  {site_id}  ERROR {str(e)[:50]}")
        return None

    df = result[0] if isinstance(result, tuple) else result
    if df is None or df.empty:
        print(f"  {site_id}  no data")
        return None

    tcol = next((c for c in ["time", "date", "datetime"] if c in df.columns), None)
    lo = str(df[tcol].min())[:10] if tcol else "?"
    hi = str(df[tcol].max())[:10] if tcol else "?"
    n = len(df)

    flag = "KEEP" if n >= MIN_ROWS else "    "
    print(f"  {flag} {site_id}  {n:>6,} rows  {lo} to {hi}")

    if n < MIN_ROWS:
        return None
    return {"gage_id": site_id, "n_days": n, "first_day": lo, "last_day": hi}


def main() -> None:
    print(f"Probing {len(CANDIDATES)} sites for daily discharge, {START} onward")
    print(f"Keeping sites with >= {MIN_ROWS:,} daily values (~10 years)\n")

    keepers = []
    for site_id in CANDIDATES:
        row = probe(site_id)
        if row:
            keepers.append(row)
        time.sleep(0.8)

    print(f"\n{len(keepers)} sites with substantial record.")

    if keepers:
        keepers.sort(key=lambda r: -r["n_days"])
        with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["gage_id", "n_days", "first_day", "last_day"])
            w.writeheader()
            w.writerows(keepers)
        print(f"Wrote {OUT_CSV}")
        total = sum(r["n_days"] for r in keepers)
        print(f"Total daily records available: {total:,}")


if __name__ == "__main__":
    main()
