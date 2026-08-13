# alpine-watch-dbt

A dbt + Snowflake analytics pipeline over USGS Water Quality Portal data
for 13 monitored alpine lakes in the Sierra Nevada and Cascades.

Built as a working reference for the patterns named in enterprise data
engineering job specs: metadata-driven ingestion, bronze/silver layering,
incremental loads with watermarking, SCD2 history, test coverage, and
Terraform-provisioned infrastructure.

---

## Architecture

```
USGS WQP REST API
      │
      │  load/ingest_wqp.py     ── Python, stage + COPY INTO
      ▼
  BRONZE.WQP_RESULTS_RAW        ── VARIANT payload, never mutated
      │
      │  dbt (staging)          ── views: cast, rename, drop garbage
      ▼
  STAGING.STG_WQP_RESULTS
      │
      │  dbt (silver)           ── incremental merge + conformed dims
      ▼
  SILVER.FCT_LAKE_MEASUREMENTS
  SILVER.DIM_LAKES
  SNAPSHOTS.SNAP_MONITORING_STATIONS
```

Bronze is append-only. Every silver table can be dropped and rebuilt from
raw with no data loss — that property is what makes backfills boring.

---

## Setup

1. **Snowflake trial** — 30 days, no card. Note your org and account name.
2. **Provision** — `cd terraform && terraform init && terraform apply`
3. **Profile** — `cp profiles.yml.example ~/.dbt/profiles.yml`, fill it in
4. **Real stations** — replace the placeholder rows in `seeds/lakes.csv`
   with your actual 13 station identifiers, or the fact table filters to
   zero rows and every test passes vacuously
5. **Run**

```bash
pixi run deps      # install dbt_utils
pixi run ingest    # populate bronze
pixi run seed      # load the watchlist
pixi run build     # seed + run + snapshot + test, in DAG order
pixi run docs      # browsable lineage graph
```

---

## Read the files in this order

Each one exists to teach a specific concept. Read the comments.

| File | Concept |
|---|---|
| `dbt_project.yml` | Materialization defaults per layer, and why they differ |
| `models/staging/_sources.yml` | `source()`, freshness thresholds tied to real cadence |
| `models/staging/stg_wqp_results.sql` | VARIANT paths, safe casting, surrogate keys |
| `models/silver/fct_lake_measurements.sql` | **The centerpiece.** Incremental merge, watermark, lookback window |
| `models/silver/_models.yml` | Generic tests: unique, not_null, relationships, accepted_values |
| `tests/assert_no_impossible_chlorophyll.sql` | Singular tests — business rules generic tests can't express |
| `snapshots/snap_monitoring_stations.sql` | SCD2, and why `check` beats `timestamp` here |
| `terraform/main.tf` | Warehouse sizing, auto-suspend, least-privilege roles |
| `load/ingest_wqp.py` | Stage + COPY INTO, VARIANT landing, batch tracing |

---

## The three ideas worth actually internalizing

**1. Idempotence is the whole game.**
`merge` on a deterministic surrogate key means running the model twice
produces the same table. Once that holds, a backfill isn't a special
procedure — it's the normal run with the filter removed.

**2. The watermark needs a lookback.**
`where _loaded_at > max(_loaded_at)` looks correct and quietly loses
data, because labs publish results weeks after the sample date. The
3-day overlap in `fct_lake_measurements.sql` is the fix, and the merge
absorbs the duplicate reads. This is the single most common incremental
bug in production.

**3. Freshness failures find breakage before anyone opens a dashboard.**
`dbt source freshness` running in CI is the cheapest monitoring you will
ever write.

---

## Deliberately not included

- Streaming ingestion (Snowpipe, Event Hubs) — different problem shape
- `--defer` / slim CI — needs prod artifacts to exist first
- Iceberg external tables — worth a follow-up once the basics land
