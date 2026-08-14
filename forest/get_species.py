"""
REF_SPECIES is a national reference table served as plain CSV, not zipped
like the state data files - hence the 404 on .zip.

Also trims it down: the national table lists every species FIA tracks
across the US, but WA_TREE only uses 57 codes. A dimension table should
cover the facts that exist, not carry 2,000 rows of species that never
appear in Washington.
"""

import pandas as pd
import requests
from pathlib import Path

OUT_DIR = Path("C:/Users/brook/Documents/fia_wa")
URL = "https://apps.fs.usda.gov/fia/datamart/CSV/REF_SPECIES.csv"

resp = requests.get(URL, timeout=300)
resp.raise_for_status()

path = OUT_DIR / "REF_SPECIES.csv"
path.write_bytes(resp.content)
print(f"downloaded {len(resp.content)/1048576:.1f} MB -> {path}")

ref = pd.read_csv(path, low_memory=False)
print(f"national species table: {len(ref):,} rows, {len(ref.columns)} columns")

tree = pd.read_csv(OUT_DIR / "WA_TREE.csv", usecols=["SPCD"], low_memory=False)
wa_codes = sorted(tree["SPCD"].dropna().unique())
print(f"species codes actually in WA_TREE: {len(wa_codes)}")

keep = ["SPCD", "COMMON_NAME", "GENUS", "SPECIES", "SPECIES_SYMBOL",
        "E_SPGRPCD", "WOODLAND", "SFTWD_HRDWD"]
cols = [c for c in keep if c in ref.columns]

wa_species = ref[ref["SPCD"].isin(wa_codes)][cols].sort_values("SPCD")
out = OUT_DIR / "WA_SPECIES.csv"
wa_species.to_csv(out, index=False)
print(f"wrote {len(wa_species)} WA species -> {out}")

print("\nMost common species in WA:")
top = tree["SPCD"].value_counts().head(10)
for spcd, n in top.items():
    row = wa_species[wa_species["SPCD"] == spcd]
    name = row["COMMON_NAME"].iloc[0] if len(row) else "?"
    print(f"  {int(spcd):>4}  {name:<32} {n:>7,} trees")
