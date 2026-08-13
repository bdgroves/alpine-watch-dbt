# THE CHASE LOG
### One day building a data warehouse out of Sierra Nevada rivers

*August 13, 2026. Lakewood, WA.*

---

## COLD OPEN

You started the morning looking at a Weyerhaeuser job posting — Data
Engineer, Seattle, Azure Data Factory into Snowflake into dbt — and
realized two things on that list were words you'd read but never touched.
By the end of the day you had a live Snowflake warehouse holding three
hundred thousand rows of real federal hydrology data, a tested star
schema, LiDAR-derived stream channels validated against a surveyed
government benchmark, and four dead hypotheses.

That last number is the important one. We'll get to it.

**They don't build these things to sit in a garage. You built it, and then
you drove it into the data to see what would happen.**

---

## THE RIG

Everything below runs on your own machine, against your own cloud account,
with no vendor holding the keys.

| Component | What it is | Status |
|---|---|---|
| **Snowflake** | `AMEJZES-CAB92741`, Enterprise trial, $400 credit | Live, 30 days |
| **`ALPINE_WATCH`** | Database — `BRONZE`, `STAGING`, `SILVER` schemas | Provisioned |
| **`ALPINE_WH`** | XSMALL warehouse, auto-suspend 60s | Costing you ~nothing |
| **`TRANSFORMER`** | Least-privilege role dbt runs as | Never ACCOUNTADMIN |
| **Terraform** | Provisions all of the above from code | 6 resources, applied |
| **Key-pair JWT** | RSA auth, no passwords | Registered |
| **pixi** | Reproducible env, ~15 tasks | One command each |
| **Repo** | `github.com/bdgroves/alpine-watch-dbt` | Pushed |

The whole thing rebuilds from `terraform apply` and `pixi install`. That's
the point. Nothing lives only in your head or only on this laptop.

---

## THE INSTRUMENT PACKAGE

Three separate data feeds, deliberately built on different cadences,
different grains, and different loading strategies — because that variety
is exactly what a real platform has to handle.

### Feed 1 — Alpine lakes (sparse, slow, chemical)
13 Sierra and Cascade lakes, USGS Water Quality Portal, bbox queries.
**1,417 rows.** Chlorophyll, Secchi depth, temperature, phosphorus.
Sparse by nature — somebody physically drives to a lake with a bottle.
Odell Lake alone is 93% of the dataset. Eight of the thirteen lakes have
no data at all, which is not a bug, it's what federal water-quality
coverage actually looks like.

### Feed 2 — Continuous streamgages (dense, fast, physical)
7 gages across Merced, Tuolumne, Stanislaus, plus Nisqually on Rainier.
**~138,000 rows** at 15-minute resolution, 90-day window.
This is telemetry. Sensors in rivers, reporting four times an hour,
some of them for over a century.

### Feed 3 — The Sierra sandbox (long, deep, historical)
14 gages, daily mean discharge, **163,566 rows spanning 1990–2026.**
Thirty-six years of record on most of them. Three river systems. Plus
NLDI basin polygons — the actual USGS-published watershed boundary for
every single gage, loaded as native `GEOGRAPHY`.

**Total in the warehouse: ~303,000 rows.** Enough that query plans start
to matter. Small enough to rebuild in fifteen seconds.

---

## THE CHASE LOG

Here's the part worth rereading. Four times today you formed a
hypothesis that sounded right, and four times the data said no.

### INTERCEPT 1 — The evening snowmelt pulse
**Predicted:** Sierra rivers should peak in the evening. Snow melts in
afternoon sun; water takes hours to reach the gage.

**Actual:** Both Merced gages peaked mid-*morning*, 8–11am, and bottomed
out around 9pm. Dead opposite.

**What it really was:** riparian evapotranspiration. Streamside vegetation
pulls water out of the shallow water table all day while photosynthesizing,
dragging flow down through the afternoon. It recovers overnight when the
plants shut off. The river breathes on a daily cycle, and it's the trees
doing the breathing, not the snow.

Amplitude at Happy Isles: ±3.8%. Downstream at Pohono Bridge: ±2.4%.
The signal damps as it travels.

### INTERCEPT 2 — The dam schedule
**Predicted:** Tuolumne near Hetch Hetchy showed violent 200 cfs drops in
single 15-minute steps. Reservoir feeding San Francisco's water supply
sits right upstream. Municipal release schedule, obviously — should cluster
on weekdays.

**Actual:** Day-of-week breakdown showed nothing. Sunday second-highest.
Thursday and Saturday zero. Only 11 events in 90 days.

**What we found instead:** dropped to raw 15-minute rows around the biggest
event (May 18, 18:30). Flow sat *dead flat* at 1,045 cfs for over an hour —
±10 cfs, pure sensor noise. Then one reading later: 839. Then immediately
flat again at a new 820 cfs plateau.

No ramp. No overshoot. No oscillation. That's a step function, and step
functions in nature are rare — that's a gate or a valve moving at a
specific moment. Real, mechanical, and *not* on a weekly schedule.
Parked unresolved. Confirming it would need SFPUC operations records.

### INTERCEPT 3 — The Rim Fire natural experiment
**Predicted:** The Rim Fire burned 257,000 acres of Tuolumne County in
August 2013. Burn scars reduce infiltration, so burned watersheds should
get flashier. Perfect before/after study.

**Actual — and this one died in stages:**

- The ideal site, Clavey River (where the fire *started*), is a
  discontinued gage. Record ends 1994.
- Jawbone Creek, SF Tuolumne, Tuolumne near Buck Meadows — every gage
  sitting squarely in the burn footprint returned **no data**.
- Wards Ferry has data, but it starts December 2013. *After* the fire.
- The one gage with complete pre/post coverage, Big Creek near Groveland,
  came back at **0.1% burned.**

**The finding:** the Rim Fire burned through a monitoring gap. The
instruments that would have measured it were decommissioned years before
it happened. That's a real, honest, publishable-in-a-footnote result, and
it kills the experiment cleanly.

Along the way it produced the sharpest methodological lesson of the day:
the Hetch Hetchy gage sits *inside* the burn perimeter, and Big Creek's
sits 3.2km *outside* — and both facts are nearly meaningless. A gage
measures everything that drains to it. Point-in-polygon answers the wrong
question entirely. You need the watershed.

### INTERCEPT 4 — Small basins are flashier
**Predicted:** Big Creek scored 0.681 on the Richards-Baker Flashiness
Index — nearly 3× every other gage — and it's the smallest basin in the
set at 16 sq mi. Small watersheds have no storage. Obvious relationship.

**Actual:** correlation of log(area) vs. flashiness came back at −0.601.
Strong! Textbook! Then we dropped Big Creek and reran: **−0.237.**

**The finding:** the correlation was one data point. With 13 remaining
gages clustered in a narrow size range, there's no relationship you could
defend. The physics is real and well-established — *these fourteen gages
just can't show it.*

**Bonus reversal inside this one:** we also predicted dam-regulated
reaches would score *high* on flashiness. Wrong again. MF Stanislaus below
Beardsley Dam is the *smoothest* gage in the entire dataset (0.072).
Reservoirs buffer flow. And critically — the gate operations from
Intercept 2 are completely invisible here, because daily averaging washes
out a 15-minute step. **Same river, same physics, opposite answer,
depending purely on time grain.** Remember that one.

---

## THE SIDE QUEST — reading rivers out of bare earth

Somewhere in the middle of all this you went to Mount Rainier.

Weyerhaeuser has a remote sensing scientist who takes LiDAR collected for
*forest inventory* and repurposes it to generate one-meter stream channel
networks. So you did the same thing, at small scale, in an afternoon:

1. **Grabbed a DEM** for the Nisqually gage area via USGS 3DEP (`py3dep`)
   — 10m resolution, seconds instead of a 34GB portal download.
2. **Ran GRASS `r.watershed`** — fill sinks, flow direction, flow
   accumulation, one call, first try.
3. **Extracted a stream network** with `r.stream.extract`.
4. **Hit a wall.** Output rendered as a mess of circles. Chased two wrong
   fixes (export type parameter, then QGIS symbology). Both wrong.
5. **Stopped guessing, queried the actual geometry** — and there it was:
   GRASS emits `Point` topology nodes mixed in with the real `LineString`
   segments. Filtered to lines only: 489 clean stream segments.
6. **Validated it.** Distance from the derived channel to the real,
   surveyed USGS gage: **62.3 meters.** About the width of a football
   field, from a 10m DEM.

That's the professional workflow, executed end to end, including the
wrong turns. The lesson from step 4–5 is worth more than the result:
*when a picture looks wrong, stop iterating on guesses and go read the
data.* Two dead hypotheses died in the time one direct query took.

---

## WHAT SNOWFLAKE AND DBT ACTUALLY DO

You asked this straight out — what does this give you that Python scripts
and GitHub Actions don't? Honest answer, no sales pitch:

**Storage and compute are separate.** ALPINE-WATCH and AFTERSHOCK run
compute and storage as one thing — a runner writes JSON to a repo.
Snowflake bills them independently. Resize a warehouse from XSMALL to
XLARGE for one heavy query and back, zero data movement. You spent
essentially nothing today because the warehouse suspends 60 seconds after
you stop typing.

**Transformations become tested software.** This is the big one, and today
proved it four separate times. Your existing pattern is a script that
computes and writes and hopes. dbt models have an explicit dependency
graph, automatic execution ordering, and tests that scream the moment
reality stops matching your assumptions. Today those tests caught:
1,257 duplicate WQP records (lab replicates), wrong unit casing
(`ug/l` vs `ug/L`), an entirely missed unit family (`RFU`), a second
phosphorus unit (`ppb`), and a join key pointed at the wrong column.
A plain script produces wrong numbers silently and you never find out.

**Semi-structured data is native.** `payload:MonitoringLocationIdentifier`
— dot-path straight into raw JSON in SQL, no flattening step. Your current
pattern parses JSON in Python before a database ever sees it.

**Incremental logic is declared, not hand-rolled.** `materialized =
'incremental'` plus `unique_key` plus `merge` replaces the "check if
exists, then update or insert" control flow you'd otherwise write by hand.
And because it's idempotent, a backfill is just the normal run with the
filter removed.

**vs. Databricks / Wherobots** (you know these): same storage/compute
split, but Snowflake removes the cluster entirely. No instance types, no
Spark tuning, no partition strategy. A warehouse is a t-shirt size. You
trade Spark's flexibility for near-zero ops surface. Storage is
proprietary micro-partitions rather than open Parquet + transaction log,
unless you specifically use Iceberg tables. Time Travel ≈ Delta time
travel, `UNDROP` ≈ `RESTORE`, zero-copy clone ≈ shallow clone — but with
no `VACUUM` to run yourself, and a 7-day Fail-safe window after Time
Travel expires that only Snowflake support can reach.

---

## THE INSTRUMENT PANEL

Functions you actually used today, not just read about:

**Window functions** — `LAG()` for day-over-day change. `PARTITION BY`
so one gage's series never bleeds into another's. `ROWS BETWEEN 3
PRECEDING AND 3 FOLLOWING` for a centered rolling mean. `QUALIFY
ROW_NUMBER()` for deduplication (in every staging model you've written).
`RANK()` for wettest-year ordering.

**Geospatial** — `TO_GEOGRAPHY`, `ST_MAKEPOINT`, `ST_DISTANCE`,
`ST_AREA`, `ST_PERIMETER`, `ST_ISVALID` as a dbt test. Gravelius
compactness ratio computed from real basin polygons.

**Statistical** — `CORR()`, `PERCENTILE_CONT()`, `MEDIAN()`. No pandas
round-trip.

**Time** — `CONVERT_TIMEZONE` (UTC → Pacific, so "hour of day" means
solar time). `DATE_TRUNC`, `DAYNAME`, `EXTRACT`. Water-year logic:
Oct 1–Sep 30, so a snowpack and its own meltwater land in the same
accounting year.

**Gotchas that cost you real time:**
- `LAG()`'s first row per partition is `NULL`, and `NULL` sorts to the
  **top** of a `DESC` order. Filter it explicitly.
- Snowflake has **no `FILTER (WHERE ...)`** clause. Use `CASE` inside the
  aggregate. Postgres and DuckDB both accept it, so it's easy to reach for.
- Double quotes are **identifiers**, not string literals. Single quotes
  for strings, always.
- `AVG()` next to a non-aggregated column needs `GROUP BY`. Snowflake
  enforces this strictly. You hit it twice.
- `dbt show` defaults to **5 rows.** Pass `--limit`.
- `dbt show --select` wants a model name; raw SQL needs `--inline`.
- `COPY INTO`'s `rowcount` reports rows-per-*file*, not rows loaded.
  It said "1 row" while loading 120,000. Check the model, not the loader.

---

## WHAT'S LOADED VS. WHAT'S SITTING ON THE BENCH

**In Snowflake, tested, working:**
- `fct_lake_measurements` — 1,417 rows, 20/20 tests
- `fct_streamflow` — ~138,000 rows, 15-min grain, 14/14 tests
- `dim_sierra_gages` — 14 basins as `GEOGRAPHY`, with shape metrics
- `fct_sierra_daily_flow` — 163,566 rows, `LAG` + rolling mean
- `fct_water_year_summary` — 425 rows, R-B flashiness, percentiles
- **22/22 tests passing on the sandbox, first run**

**Downloaded but NOT loaded yet:**
- 575 CAL FIRE perimeters (`tuolumne_fire_perimeters.geojson`) — the
  `ST_INTERSECTS` spatial join against those basins is sitting right
  there waiting for you
- 489 Nisqually stream segments — models written
  (`stg_derived_streams`, `fct_gage_stream_validation`), loader written,
  **never run**

**The test that should make you happiest:**
`assert_basin_area_matches_usgs` — compares your `ST_AREA` calculation
against USGS's own independently published drainage area, fails past 25%
divergence. It passed on all 14. That single test validates the entire
geospatial chain: WKT export, CRS handling, GEOGRAPHY cast, geodesic area.
Two independent measurements of the same physical basin agreeing is how
you know the polygons are real and not garbage that merely renders nicely.

---

## NEXT CHASE

**Immediate, cheap:**
- Load those 575 fire perimeters, run `ST_INTERSECTS` against the 14
  basins. Which Sierra watersheds have burned, ever, and how much?
- Run `pixi run docs` — you've never seen the lineage graph, and there
  are three pipelines in it now
- Run the Nisqually stream load that's still pending

**Real skill gaps still open:**
- Query Profile in Snowsight (you've never opened it — 163K rows is
  enough to see a real plan)
- Streams + Tasks — Snowflake's native CDC, and the posting names CDC
  explicitly
- Time Travel / `UNDROP`, tried on purpose against a throwaway table
- Zero-copy clone — clone ALPINE_WATCH, watch it cost nothing
- `--defer` slim CI, once a prod target exists
- The `relationships` / `freshness` deprecation warnings — fix them
  yourself, it forces you to read the schema change

**Housekeeping:**
- Regenerate the Snowflake key pair (passphrase went into a chat window)
- `setx` the env vars so they survive new terminals
- Trial clock: **30 days from Aug 12.** You've spent almost nothing.

---

## THE THING TO REMEMBER

Four hypotheses died today. Evening snowmelt, dam schedules, the Rim Fire
experiment, small-basin flashiness. Every one of them sounded right when
you formed it.

That's not a bad day. That's the job. The reason it cost minutes instead
of weeks is that the metrics were already modeled, already tested, already
sitting in a warehouse where the next question was one query away.

A notebook would have let every one of those wrong answers through.

**You're not chasing the answer. You're building the thing that tells you
when you're wrong.**

*— end of log, Aug 13, 2026*
