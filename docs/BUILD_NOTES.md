# alpine-watch-dbt — Build Notes

*For future Brooks. Updated after adding the Sierra Nevada streamflow pipeline, August 2026.*

## Why this exists

Two gaps against the Weyerhaeuser Data Engineer posting: **dbt** and
**Snowflake**, plus a Terraform refresher. Airflow experience already covers
orchestration — ADF is a syntax change on the same concepts. Rather than do
tutorials, we built one real project against data you already understood,
then a second pipeline against much denser data once the first one exposed
how sparse WQP grab samples actually are.

Repo: `github.com/bdgroves/alpine-watch-dbt`

## What we actually built — now two pipelines, one warehouse

```
Pipeline 1: Lake water quality (sparse, grab samples)
USGS WQP (bbox query per lake, 4 characteristics)
      │
      ▼
BRONZE.WQP_RESULTS_RAW → staging → SILVER.FCT_LAKE_MEASUREMENTS
      13 lakes, 1,417 rows total

Pipeline 2: Sierra Nevada streamflow (dense, continuous telemetry)
USGS Water Data API — waterdata.get_continuous(), 15-min intervals
      │
      ▼
BRONZE.STREAMFLOW_CONTINUOUS_RAW → staging → SILVER.FCT_STREAMFLOW
      6 gages × 3 parameters, ~120,000 rows, 90-day window
```

Both pipelines share one Terraform-provisioned warehouse, database, and
`TRANSFORMER` role — the second pipeline needed **zero new infrastructure**,
because the original grant was scoped at the `BRONZE` schema level, not
per-table. That's the payoff of doing the permissions model properly the
first time.

## The build log — pipeline 2 additions

1. **Found the real gages** — not guessed. Web-searched and verified six
   currently-active USGS site numbers spanning Merced, Tuolumne, and
   Stanislaus rivers, mirroring ALPINE-WATCH's own alpine-anchor /
   valley-comparison pairing logic (Odell vs. Waldo → Happy Isles vs.
   Pohono Bridge, etc.).

2. **Caught an API migration before building on the wrong thing.** USGS is
   retiring the legacy NWIS WaterServices API (the one `dataretrieval.nwis`
   is built on) — full decommission Q1 2027, degradation possibly starting
   as early as this month. Built against the new `waterdata` module instead,
   which `dataretrieval-python` added specifically as the migration target.
   Worth naming in an interview: *"I checked whether the API I was about to
   depend on was stable before committing to it."*

3. **Designed around uncertainty differently than pipeline 1.** The WQP
   pipeline trusted the API's raw column names and got bitten by the
   unit_code guess. This time, the loader inspects `df.columns` at runtime
   and normalizes into a schema we define ourselves *before* it reaches
   Snowflake — bronze holds a contract we control, not a pass-through of an
   external API's naming choices.

4. **`COPY INTO` rowcount is not what it looks like.** The loader reported
   "loaded 1 rows" despite 120,820 records actually landing correctly.
   `cur.rowcount` after a `COPY INTO` reflects rows-per-source-file, not
   total data rows — a reporting quirk, not data loss. Confirmed by building
   the models and seeing real counts; the WQP loader has the identical
   latent bug, just never surfaced because nobody looked closely.

5. **Ambiguous column name in an ad-hoc query.** `fct_streamflow` already
   carries `gage_name` (joined in during the model build) — re-joining
   `dim_gages` in a follow-up query created two columns with the same name.
   Small, but a good example of forgetting your own model's grain.

6. **One gage returned zero data across all three parameters** — Long Barn
   (11298000). Not investigated yet; the source citation for that gage was
   a 2013 report, so it may simply be inactive now. Left as a real "no data"
   state rather than chased down, same posture as ALPINE-WATCH's own
   no-data lakes.

## What Snowflake and dbt actually do differently

You asked the honest question — what does this stack give you that your
existing Python/pandas/GitHub Actions workflow doesn't? Real answer, not a
sales pitch:

**Storage and compute are separate.** Your JSON-file pipelines (ALPINE-WATCH,
AFTERSHOCK, etc.) run compute and storage as one thing — a GitHub Actions
runner writes files to a repo. Snowflake's warehouse (compute) and database
(storage) are billed and scaled completely independently. You can resize a
warehouse from XSMALL to XLARGE for one heavy query and back down, with zero
data movement — trying that with files-on-disk means literally moving data.

**Transformation becomes tested, documented, version-controlled software**,
not a script that runs and hopes. Your existing pattern is a Python script
that computes something and writes JSON. dbt models are SQL with an explicit
dependency graph (`ref()`), automatic execution ordering, and tests that
fail loudly the moment reality stops matching assumptions — which is exactly
what caught the WQP duplicates, the bad unit casing, and the join-key bug in
this project. A plain script would have just silently produced wrong numbers.

**Semi-structured data lives natively in the warehouse.** The `VARIANT`
type let us dot-path into raw JSON (`payload:MonitoringLocationIdentifier`)
directly in SQL, no separate flattening step before it's queryable. Your
current pattern parses JSON in Python before anything touches a database.

**Incremental logic is a declared strategy, not hand-rolled control flow.**
`materialized='incremental'` + `unique_key` + `merge` replaces what would
otherwise be manually-written "check if it exists, then update or insert"
Python logic — and it composes with the dependency graph automatically.

**Two things we haven't touched yet, worth knowing exist:** Time Travel
(query any table as of any point in the last N days, or `UNDROP` something
you deleted by accident — no backup system required) and zero-copy cloning
(instantly clone an entire database for testing without duplicating storage).
Neither has a real equivalent in a file-based pipeline.

## Left undone (not urgent, listed so it doesn't nag)

- `COPY INTO` rowcount reporting bug in both loaders — cosmetic (logs a
  wrong number), doesn't affect correctness. Worth understanding the fix,
  not high priority.
- Long Barn gage (11298000) — check `waterdata.get_monitoring_locations()`
  to see if it's inactive or just miscoded.
- `relationships` and `freshness` deprecation warnings — dbt schema syntax
  changes, will become hard errors eventually.
- Phosphorus unit conversion (`ppb` → `mg/L`) for cross-lake comparability.
- GitHub Actions workflow exists but isn't wired to secrets yet — everything
  still runs by hand.
- `LOOKBACK_DAYS = 90` in the streamflow loader — these gages have records
  back to 1915; widening this is the real test of the incremental merge at
  historical scale.
- `--defer` for slim CI — needs a prod target to defer against.

## TODO — skills to build, now spanning both pipelines

**Snowflake**
- [ ] Warehouse sizing & auto-suspend — understand *why* XSMALL/60s were
      reasonable defaults here, not just that they worked
- [ ] Query profile — run something slow on purpose (try an unfiltered scan
      of `fct_streamflow`, 120K rows is enough to see a real profile), read
      the bottleneck step
- [ ] Role hierarchy — the full `ACCOUNTADMIN` → `SECURITYADMIN`/`SYSADMIN`
      → custom role tree, so the `CREATE ROLE` wall never surprises you again
- [ ] Time Travel / `UNDROP` — try it on purpose against a throwaway table
- [ ] Streams + Tasks — Snowflake's native CDC primitives; directly relevant
      since the posting names CDC explicitly
- [ ] Zero-copy cloning — clone `ALPINE_WATCH` into a scratch database,
      see what it costs (should be near-instant, near-free)

**dbt**
- [ ] Fix the `relationships` deprecation yourself — nest args under
      `arguments:` in both `_models.yml` files
- [ ] Fix the `freshness` deprecation — move it under `config:` per the
      warning
- [ ] Write one more singular test from scratch, unaided
- [ ] `dbt docs generate` — actually read the lineage graph now that there
      are two pipelines to see side by side in it
- [ ] Try a *different* incremental strategy (`delete+insert`) on a copy of
      `fct_streamflow`, compare behavior against `merge`
- [ ] Exposures — document that a model "feeds a dashboard," even
      hypothetically

**Terraform**
- [ ] Remote state — read how S3/Azure backend + locking works, even without
      implementing it (local state is fine solo, wrong for a team)
- [ ] `terraform destroy` on a throwaway resource, on purpose

**This project specifically**
- [ ] Investigate Long Barn's zero-data result
- [ ] Set `$env:API_USGS_PAT` permanently via `setx`
- [ ] Widen `LOOKBACK_DAYS` and watch the incremental merge handle real scale
- [ ] Wire GitHub Actions secrets so both `pixi run ingest*` + `build`
      actually run on a schedule instead of by hand

## Quick reference

```powershell
cd C:\Users\brook\Documents\alpine-watch-dbt

$env:SNOWFLAKE_ACCOUNT = "AMEJZES-CAB92741"
$env:SNOWFLAKE_USER = "BDGROVES"
$env:SNOWFLAKE_PRIVATE_KEY_PATH = "C:\Users\brook\.snowflake\keys\rsa_key.p8"
$env:SNOWFLAKE_PRIVATE_KEY_PASSPHRASE = "<the one you set>"
$env:API_USGS_PAT = "<your USGS key>"

pixi run dbt debug        # confirm connection
pixi run ingest            # re-pull WQP lake data
pixi run ingest-streamflow # re-pull streamgage data
pixi run build              # dbt build: both pipelines + all tests
pixi run docs                # browsable lineage graph, now with 2 pipelines
```

Snowflake trial: **30 days from Aug 12, 2026** — $400 credit. At this data
volume (~122K rows total across both pipelines) you are nowhere close to
spending it meaningfully; the constraint here was never cost, it was
learning surface area.

## A real investigation, worth remembering as an example

This is the story worth telling in an interview if asked "walk me through a
time you found something unexpected in data." It happened in one sitting,
using nothing but `LAG()`, `PARTITION BY`, and a `WHERE` clause.

**1. Started with a hunch, and it was wrong.** Averaged Merced River
discharge by hour of day, expecting an evening peak (snowmelt takes hours to
travel from high elevation to the gage). Instead found a morning peak
(~8-11am) and evening trough (~8-9pm) at both gages on the river. The actual
driver is riparian evapotranspiration — streamside vegetation pulls water
from the shallow water table while photosynthesizing in daylight, dropping
flow through the afternoon, recovering overnight. Wrong hypothesis, real
signal, more interesting than the original guess.

**2. Noticed an anomaly rather than smoothing past it.** Both Merced gages
showed an odd upward blip at hour 17 that broke the otherwise smooth curve.
Formed a hypothesis: single storm event skewing the average.

**3. Tested the hypothesis with a follow-up query, and it survived — but
differently than expected.** Isolating the specific dates behind hour 17
showed four consecutive days (May 15-18) with dramatically elevated flow,
declining smoothly. Not a storm — the tail end of spring snowmelt recession,
sitting inside a 90-day window that otherwise captured summer baseflow.
Lesson: know what regime your window is actually sampling before trusting
an average across it.

**4. Used `LAG()` to hunt for the sharpest single-step changes anywhere in
the streamflow data** (the Richards-Baker Flashiness Index concept — how
"jumpy" a river's flow is). Nearly all the biggest jumps clustered at one
gage: Tuolumne near Hetch Hetchy, 100-200 cfs in a single 15-minute step.

**5. Formed a second hypothesis — dam-operated release schedule — and killed
it with data.** Hetch Hetchy Reservoir sits upstream and feeds San Francisco's
water supply, so a weekday-heavy pattern seemed likely. A day-of-week
breakdown of big jumps showed no such pattern (Sunday second-highest,
Thursday and Saturday zero) — hypothesis rejected, and said so rather than
forcing a story onto a null result.

**6. Looked at the raw shape instead of aggregating further.** Pulled the
biggest single jump (May 18, 18:30, -201 cfs) at 15-minute resolution: dead
flat at ~1,045 cfs for over an hour, one instant drop to 839, then
immediately flat again at a new ~820 cfs plateau. That step-function shape
(no ramp, no overshoot) rules out weather or snowmelt and points to a
discrete operational event — a gate or valve change, not tied to a simple
weekly schedule. Parked there; confirming further would need SFPUC
reservoir operation records, outside this project's scope.

**The pattern worth reusing**: form a hypothesis → write the smallest query
that tests it → let a rejected hypothesis be a real answer, not a reason to
torture the data into agreeing → when aggregates get ambiguous, drop down to
raw rows and look at the actual shape.

## Snowflake concepts touched in this session

- `LAG()` / `PARTITION BY` / `ORDER BY` — window functions, no self-join needed
- `QUALIFY` — already embedded in every staging model's dedup logic
- `CONVERT_TIMEZONE` — UTC to Pacific for solar-time analysis
- `DATE_TRUNC`, `DAYNAME`, `EXTRACT(hour from ...)` — time bucketing
- Aggregate + `GROUP BY` rules — `AVG()` alongside a non-aggregated column
  needs the group by; Snowflake enforces this strictly (hit this twice)
- `NULL` sort behavior — `LAG()`'s first row per partition is `NULL`, and
  `NULL` sorts to the top of a `DESC` order by default. Filter it out
  explicitly rather than assume it'll land at the bottom.

Not yet touched, queued for next time: `CORR()`/statistical functions,
`ASOF JOIN` (matching the two pipelines' different time grains), `ST_`
geospatial functions.
