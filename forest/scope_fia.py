"""
Scope the Washington FIA data before committing to a load.

Same discover-then-build pattern that's worked all session: download,
report actual row counts and column names, THEN decide what the models
should look like. WA_TREE in particular could be millions of rows and
it's worth knowing that before designing around it.

Downloads to disk and leaves the files there - no Snowflake connection,
no bronze tables, nothing destructive.

FIA DataMart URL pattern (verified against FIESTA R package docs and
multiple independent sources):
    https://apps.fs.usda.gov/fia/datamart/CSV/{STATE}_{TABLE}.zip
REF_SPECIES is national, no state prefix.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd
import requests

BASE = "https://apps.fs.usda.gov/fia/datamart/CSV"
STATE = "WA"
OUT_DIR = Path("C:/Users/brook/Documents/fia_wa")

# The four tables that form the star schema.
TABLES = {
    f"{STATE}_PLOT": "plot locations, survey years, elevation",
    f"{STATE}_COND": "forest type, ownership, stand age per condition",
    f"{STATE}_TREE": "one row per tree per measurement - the big one",
    "REF_SPECIES": "national species code lookup",
}

# Columns worth reporting on if present - the ones the models will use.
INTERESTING = {
    "CN", "PLT_CN", "STATECD", "COUNTYCD", "PLOT", "INVYR", "MEASYEAR",
    "LAT", "LON", "ELEV", "PLOT_STATUS_CD",
    "CONDID", "COND_STATUS_CD", "FORTYPCD", "STDAGE", "OWNCD", "OWNGRPCD",
    "SPCD", "DIA", "HT", "ACTUALHT", "STATUSCD", "TPA_UNADJ",
    "CARBON_AG", "DRYBIO_AG", "TOTAGE",
    "COMMON_NAME", "GENUS", "SPECIES", "SPECIES_SYMBOL",
}


def fetch(table: str) -> pd.DataFrame | None:
    url = f"{BASE}/{table}.zip"
    print(f"\n=== {table} ===")
    print(f"  {url}")

    try:
        resp = requests.get(url, timeout=900, stream=True)
        resp.raise_for_status()
        content = resp.content
    except Exception as e:
        print(f"  FAILED: {str(e)[:100]}")
        return None

    mb = len(content) / 1_048_576
    print(f"  downloaded {mb:,.1f} MB compressed")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = OUT_DIR / f"{table}.zip"
    zip_path.write_bytes(content)

    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        names = zf.namelist()
        print(f"  contains: {names}")
        with zf.open(names[0]) as fh:
            df = pd.read_csv(fh, low_memory=False)

    print(f"  ROWS: {len(df):,}   COLUMNS: {len(df.columns)}")

    present = [c for c in df.columns if c in INTERESTING]
    print(f"  key columns present: {present}")

    missing = INTERESTING - set(df.columns)
    relevant_missing = [
        c for c in missing
        if any(c.startswith(p) for p in ("SPCD", "DIA", "HT", "LAT", "LON", "FORTYP"))
    ]
    if relevant_missing:
        print(f"  (not in this table: {relevant_missing})")

    # Save uncompressed for the loader to read later
    csv_path = OUT_DIR / f"{table}.csv"
    df.to_csv(csv_path, index=False)
    print(f"  saved -> {csv_path}")

    return df


def main() -> None:
    print(f"Scoping FIA data for {STATE}")
    print(f"Output directory: {OUT_DIR}")

    frames = {}
    for table, desc in TABLES.items():
        print(f"\n[{desc}]")
        df = fetch(table)
        if df is not None:
            frames[table] = df

    print("\n" + "=" * 55)
    print("SUMMARY")
    print("=" * 55)
    total = 0
    for table, df in frames.items():
        print(f"  {table:<16} {len(df):>10,} rows")
        total += len(df)
    print(f"  {'TOTAL':<16} {total:>10,} rows")

    # Quick look at what's actually in the tree table
    tree_key = f"{STATE}_TREE"
    if tree_key in frames:
        t = frames[tree_key]
        print(f"\nTree table detail:")
        if "INVYR" in t.columns:
            print(f"  inventory years: {int(t['INVYR'].min())} - {int(t['INVYR'].max())}")
        if "SPCD" in t.columns:
            print(f"  distinct species codes: {t['SPCD'].nunique()}")
        if "STATUSCD" in t.columns:
            counts = t["STATUSCD"].value_counts().head(4).to_dict()
            print(f"  status codes (1=live, 2=dead): {counts}")
        if "DIA" in t.columns:
            print(f"  diameter range: {t['DIA'].min():.1f} - {t['DIA'].max():.1f} inches")

    print("\nNothing loaded to Snowflake yet - this was scoping only.")


if __name__ == "__main__":
    main()
