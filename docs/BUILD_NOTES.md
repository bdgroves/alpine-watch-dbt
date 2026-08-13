# alpine-watch-dbt — Build Notes

*For future Brooks. Written after finishing the first full green build, August 2026.*

## Why this exists

You had two gaps against the Weyerhaeuser Data Engineer posting: **dbt** and
**Snowflake**, with Terraform needing a refresher. Airflow experience covered
the orchestration requirement — ADF is a syntax change on the same concepts.
Rather than do three separate tutorials, we built one real project that hits
all three, using ALPINE-WATCH's own 13-lake water quality data as the source
so you were modeling something you already understood instead of a toy
dataset.

Repo: `github.com/bdgroves/alpine-watch-dbt`

## What we actually built

```
USGS WQP (bbox query per lake, 4 characteristics)
      │
      │  load/ingest_wqp.py  — dataretrieval-python, stage + COPY INTO
      ▼
BRONZE.WQP_RESULTS_RAW        — VARIANT, append-only, never mutated
      │
      │  dbt staging          — flatten, dedupe, type cast
      ▼
STAGING.STG_WQP_RESULTS
      │
      │  dbt silver           — incremental merge, 3-day lookback
      ▼
SILVER.FCT_LAKE_MEASUREMENTS  — 1,417 rows, 13 lakes, 4 characteristics
SILVER.DIM_LAKES              — 13-row curated dimension
```

Infrastructure (warehouse, database, schema, role, grants) is Terraform-
managed. Auth is key-pair (JWT), not password. Everything runs through pixi
so the environment is reproducible — same pattern as your other projects.

## The build log — what actually happened

This is the part worth rereading before an interview. None of this was a
clean first-try tutorial; every fix below is a real bug you can talk about.

1. **Environment setup** — GitHub repo pushed from Windows via git (not the
   iPad drag-and-drop approach, which turned out unreliable for nested
   folders). pixi installed the dbt/Snowflake toolchain locally.

2. **Snowflake key-pair auth** — generated an encrypted RSA key pair with
   OpenSSL (via Git Bash, since Windows PowerShell doesn't ship OpenSSL),
   registered the public key against your Snowflake user with
   `ALTER USER ... SET RSA_PUBLIC_KEY`. This is the auth pattern real
   production pipelines use — password auth is being phased out industry-wide.

3. **Terraform provider auth mismatch** — the Snowflake Terraform provider
   defaults to password auth unless you explicitly set
   `authenticator = "SNOWFLAKE_JWT"` plus `private_key` (file *contents*,
   not a path) and `private_key_passphrase`. Silent trap — the error message
   ("password is empty") doesn't obviously point at the fix.

4. **Role hierarchy gap** — `SYSADMIN` can't `CREATE ROLE` by default; that's
   `SECURITYADMIN`'s job. Fixed by using `ACCOUNTADMIN` (fine for a
   single-user trial; wrong answer on a real team, where you'd request the
   specific grant instead of reaching for the top role).

5. **The architecture rethink** — this was the real lesson. The original
   design assumed ALPINE-WATCH pulled data by fixed USGS station ID. Reading
   the actual `fetch_lakes.py` showed it queries by **lat/lon bounding box**
   per lake instead — a lake's identity comes from which query returned the
   record, not from any field in the data. Had to rework `dim_lakes`, the
   staging model, and the fact table's join key from `station_id` to
   `lake_id`. This is the single best interview story from the whole
   project: *"I found my assumed schema didn't match the real source system,
   and reworked the join key rather than forcing bad data through."*

6. **Real WQP data quality issues, found by tests actually failing:**
   - **1,257 duplicate `measurement_sk` values** — WQP sends real duplicates
     (lab replicates, multi-org submissions) for the same
     station/date/characteristic/unit. Fixed with `qualify row_number()`
     in staging, keeping one deterministically.
   - **Unit casing wrong** — assumed `ug/l`, actual data has `ug/L`.
   - **A whole unit family missed** — `RFU` (relative fluorescence units),
     how some sensors report chlorophyll instead of lab-derived µg/L.
   - **A second unit for phosphorus** — `ppb` alongside `mg/L`. Flagged but
     not fixed (see "left undone" below) — this is a downstream conversion
     problem, not a data quality one.

7. **Tooling friction, for the résumé-adjacent "I can debug my own
   environment" pile:** PowerShell here-string escaping corrupted a SQL
   file (`@"..."@` interprets backslash-quote; `@'...'@` doesn't) — a good
   example of environment-specific gotchas that don't show up until you hit
   them. `dbt show --select` vs `--inline` — select wants a model name, not
   raw SQL.

## Mapping to the Weyerhaeuser posting

| Posting requirement | Where you now have it |
|---|---|
| Python + SQL | Already had it. `ingest_wqp.py`, every model. |
| ADF / comparable orchestration | Airflow (existing) + this project's dbt/pixi orchestration concepts transfer directly. |
| **dbt** — materializations, tests, docs, history | View/table/incremental all used with reasoning for each. 16 generic tests + 1 singular business-rule test. `dbt docs` lineage graph. |
| **Snowflake** — loading, RBAC, cost-aware design | `COPY INTO` bulk load (not row inserts), `TRANSFORMER` role scoped to exactly what it needs, `auto_suspend`/`auto_resume` on the warehouse. |
| Incremental/delta patterns — watermarking, CDC, backfills | `is_incremental()` + merge on surrogate key + 3-day lookback window for late-arriving lab results. Idempotent — a backfill is just a full-refresh run. |
| Terraform | Real refresher: provider auth, role hierarchy, resource/variable/output split, all against a real target instead of a tutorial sandbox. |
| Data quality, monitoring | `dbt source freshness`, generic + singular tests, all of which caught *real* issues in this build (see above). |
| Geospatial exposure (preferred) | The whole bbox/lat-lon join rework *is* geospatial reasoning, even without PostGIS-style functions. Worth naming explicitly in an interview. |
| Git/PR/CI-CD | Repo pushed, `.github/workflows/dbt.yml` scaffolded (not yet wired to secrets — see below). |
| AI-assisted development | This whole project. Worth being straightforward about in an interview — the posting explicitly wants this, not something to downplay. |

**Still a real gap:** SAP source ingestion — nothing substitutes for this,
probably fine to just not have. Iceberg table structures — untouched.
Streaming/near-real-time (Event Hubs/Kafka) — untouched, and this project's
twice-weekly batch cadence is intentionally the opposite of that pattern.

## Left undone on purpose (not urgent, listed so it doesn't nag)

- Phosphorus unit conversion (`ppb` → `mg/L`) for cross-lake comparability —
  belongs in a downstream mart, not silver.
- `relationships` test deprecation warning — needs args nested under
  `arguments:` per newer dbt schema. Cosmetic today, will become a hard
  error eventually.
- GitHub Actions workflow exists but isn't wired to Snowflake secrets yet —
  currently everything runs by hand.
- `--defer` for slim CI — needs a prod target to defer against, which
  doesn't exist yet.

## Quick reference for picking this back up

```powershell
cd C:\Users\brook\Documents\alpine-watch-dbt

# per-session, since $env: vars don't persist across PowerShell windows
$env:SNOWFLAKE_ACCOUNT = "AMEJZES-CAB92741"
$env:SNOWFLAKE_USER = "BDGROVES"
$env:SNOWFLAKE_PRIVATE_KEY_PATH = "C:\Users\brook\.snowflake\keys\rsa_key.p8"
$env:SNOWFLAKE_PRIVATE_KEY_PASSPHRASE = "<the one you set>"

pixi run dbt debug   # confirm connection still works
pixi run ingest      # re-pull from WQP (few minutes, rate-limited)
pixi run build        # dbt build: staging + fact + all tests
pixi run docs         # browsable lineage graph
```

Snowflake trial: **30 days from Aug 12, 2026** — $400 credit, essentially
unusable to burn through at this scale. Worth checking before it lapses
whether continuing past the trial is worth it, or whether this project has
done its job as a portfolio/skill-building piece by then.
