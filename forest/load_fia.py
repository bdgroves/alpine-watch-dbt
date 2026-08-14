"""
Load Washington FIA into Snowflake bronze.

Deliberately different from the other loaders in this repo: the WQP and
streamflow feeds arrive as JSON from APIs whose schemas we don't control,
so VARIANT made sense there. FIA arrives as CSV with a stable, documented
schema (the FIADB User Guide), so bronze gets real typed columns.

Also selects ~15 columns out of 198. FIA tables are extremely wide and
most of it is inventory bookkeeping we'll never query. Landing everything
"just in case" makes every downstream scan more expensive forever.
"""

from __future__ import annotations

import gzip
import os
import tempfile
from pathlib import Path

import pandas as pd
import snowflake.connector

SRC = Path("C:/Users/brook/Documents/fia_wa")

# Column selections. Anything not present in the file is skipped with a
# warning rather than crashing - FIA schemas drift between versions.
SPECS = {
    "FIA_WA_PLOT_RAW": {
        "file": "WA_PLOT.csv",
        "cols": [
            "CN", "STATECD", "UNITCD", "COUNTYCD", "PLOT", "INVYR",
            "MEASYEAR", "PLOT_STATUS_CD", "LAT", "LON", "ELEV",
        ],
        "ddl": """
            cn              varchar,
            statecd         integer,
            unitcd          integer,
            countycd        integer,
            plot            integer,
            invyr           integer,
            measyear        integer,
            plot_status_cd  integer,
            lat             float,
            lon             float,
            elev            float
        """,
    },
    "FIA_WA_COND_RAW": {
        "file": "WA_COND.csv",
        "cols": [
            "CN", "PLT_CN", "INVYR", "CONDID", "COND_STATUS_CD",
            "FORTYPCD", "STDAGE", "OWNCD", "OWNGRPCD", "SITECLCD",
            "SLOPE", "ASPECT", "CONDPROP_UNADJ",
        ],
        "ddl": """
            cn              varchar,
            plt_cn          varchar,
            invyr           integer,
            condid          integer,
            cond_status_cd  integer,
            fortypcd        integer,
            stdage          integer,
            owncd           integer,
            owngrpcd        integer,
            siteclcd        integer,
            slope           integer,
            aspect          integer,
            condprop_unadj  float
        """,
    },
    "FIA_WA_TREE_RAW": {
        "file": "WA_TREE.csv",
        "cols": [
            "CN", "PLT_CN", "PREV_TRE_CN", "CONDID", "INVYR",
            "STATUSCD", "SPCD", "DIA", "HT", "ACTUALHT", "TOTAGE",
            "TPA_UNADJ", "CARBON_AG", "DRYBIO_AG", "CCLCD",
        ],
        "ddl": """
            cn           varchar,
            plt_cn       varchar,
            prev_tre_cn  varchar,
            condid       integer,
            invyr        integer,
            statuscd     integer,
            spcd         integer,
            dia          float,
            ht           float,
            actualht     float,
            totage       float,
            tpa_unadj    float,
            carbon_ag    float,
            drybio_ag    float,
            cclcd        integer
        """,
    },
}

DB_SCHEMA = "ALPINE_WATCH.BRONZE"


def connect():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
        private_key_file_pwd=os.environ["SNOWFLAKE_PRIVATE_KEY_PASSPHRASE"].encode(),
        role="TRANSFORMER",
        warehouse="ALPINE_WH",
        database="ALPINE_WATCH",
        schema="BRONZE",
    )


def load_table(cur, table: str, spec: dict) -> None:
    src = SRC / spec["file"]
    print(f"\n-- {table} --")
    print(f"  reading {src.name}")

    header = pd.read_csv(src, nrows=0)
    available = [c for c in spec["cols"] if c in header.columns]
    missing = [c for c in spec["cols"] if c not in header.columns]
    if missing:
        print(f"  WARNING: columns not in file, skipping: {missing}")

    id_cols = {"CN", "PLT_CN", "PREV_TRE_CN"}
    dtypes = {c: str for c in available if c in id_cols}
    df = pd.read_csv(src, usecols=available, dtype=dtypes, low_memory=False)
    # Reorder to match the DDL, dropping any that were missing
    df = df[available]
    print(f"  {len(df):,} rows x {len(df.columns)} columns")

    # Rebuild DDL to match only the columns we actually have
    ddl_lines = [
        line.strip().rstrip(",")
        for line in spec["ddl"].strip().split("\n")
        if line.strip()
    ]
    ddl_map = {l.split()[0].upper(): l for l in ddl_lines}
    ddl = ",\n            ".join(ddl_map[c.upper()] for c in available)

    cur.execute(f"create or replace table {DB_SCHEMA}.{table} (\n            {ddl}\n        )")

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"{table}.csv.gz"
        # Write without header - COPY INTO with skip_header=0 on a
        # headerless file is less fragile than relying on column order
        # matching a header we then have to skip.
        with gzip.open(path, "wt", encoding="utf-8", newline="") as fh:
            df.to_csv(fh, index=False, header=False)

        cur.execute(f"put file://{path} @%{table} auto_compress=false")
        cur.execute(f"""
            copy into {DB_SCHEMA}.{table}
            from @%{table}
            file_format = (
                type = csv
                field_delimiter = ','
                skip_header = 0
                field_optionally_enclosed_by = '"'
                empty_field_as_null = true
                compression = gzip
            )
            on_error = 'abort_statement'
            purge = true
        """)

    cur.execute(f"select count(*) from {DB_SCHEMA}.{table}")
    n = cur.fetchone()[0]
    print(f"  loaded {n:,} rows into {table}")


def main() -> None:
    print("Loading Washington FIA into Snowflake bronze")

    conn = connect()
    try:
        cur = conn.cursor()
        for table, spec in SPECS.items():
            load_table(cur, table, spec)
        conn.commit()
    finally:
        conn.close()

    print("\nDone. Species dimension goes in as a dbt seed separately.")


if __name__ == "__main__":
    main()
