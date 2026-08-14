# THE FIRE CHAPTER
### What 440 burned plots say about wildfire in Washington

*August 14, 2026 — day two*

---

## THE SETUP

Yesterday the Rim Fire investigation died. Not because the science was
wrong — because the instruments weren't there. Every streamgage inside
that 257,000-acre burn had been decommissioned years before it happened.
Clavey River: record ends 1994. Jawbone Creek: nothing. The fire burned
straight through a monitoring gap and there was no way to measure it.

Today we came back at the same question from a completely different angle,
and it worked. Here's why:

**Streamgages get shut off. FIA plots don't.**

The Forest Inventory and Analysis program revisits every plot on a fixed
cycle regardless of what happens to it. Burn a plot to the ground and a
crew still shows up on schedule to measure whatever is left. That means a
plot that burned in 2014 and got remeasured in 2019 carries **its own
pre-fire baseline**.

That's the natural experiment. No control group needed — each plot is its
own control.

---

## THE HAUL

**4,921** fire perimeters pulled from NIFC's InterAgencyFirePerimeterHistory,
clipped to Washington. Conglomerated from USFS, BLM, BIA, FWS, NPS, CalFire
and WFIGS.

After conforming: **1,788** usable fires. Two-thirds of the raw records
were duplicates, reconstructions, or junk.

**2,238** plot-fire spatial matches.
**874** distinct plots that have burned at least once.
**440** plots measured on *both sides* of the same fire.

That last number is the one that mattered.

---

## WHAT THE FIRE DID

Plots measured before and after, average 11-year remeasurement interval:

| Fire size | Plots | Dead stems before | Dead stems after | Change |
|---|---|---|---|---|
| Megafire (100k+ ac) | 203 | 16.1% | **73.9%** | +57.8 |
| Large (10k–100k ac) | 185 | 21.6% | **71.5%** | +49.9 |
| Moderate (1k–10k ac) | 45 | 21.8% | **60.8%** | +39.0 |

And standing live biomass, computed as ratio of totals:

| Fire size | Before (tons) | After (tons) | Change |
|---|---|---|---|
| Megafire | 9,312 | 3,020 | **−67.6%** |
| Large | 9,989 | 3,762 | **−62.3%** |
| Moderate | 2,601 | 1,528 | **−41.3%** |

**A megafire takes about two-thirds of the standing wood and leaves three
out of four stems dead.** Measured. On identified plots. Not modeled.

Both gradients run clean and monotonic with fire size.

---

## THE PART WHERE I WAS WRONG (AGAIN)

Called it before running it: biomass loss should scale with fire size.

First cut said no — megafires lost 22.0 tons/acre, large fires 21.5,
moderate 19.7. Nearly identical. Size class appeared to do nothing.

Wrong variable. **Biomass change over an 11-year window mixes three things
together**: fire mortality, subsequent regrowth, and snags falling over.
Mortality *share* is the cleaner instrument, and it showed the gradient
immediately — 57.8 / 49.9 / 39.0.

Then the percentage biomass number came back at **+12.4%** for large fires.
A biomass *gain*, on plots where 71.5% of stems were dead. Impossible.

Cause: **averaging ratios is not the ratio of totals.** `pct_biomass_change`
is a per-plot ratio, and when a plot's starting biomass is near zero the
ratio explodes — one plot going 0.5 → 5 tons/acre registers +900% and drags
185 plots' worth of mean with it. The `nullif` guarded against division by
zero but not against near-zero denominators.

Aggregate first, then divide: −62.3%. Median as a cross-check: −41.3%.
Both negative, both sensible. The mean-of-ratios hadn't just been noisy —
it pointed the wrong direction.

**File that one permanently.** It's a standard trap and it produces a
number that looks like a finding.

---

## WHAT THE DATA WON'T TELL YOU

Three real limits, stated plainly:

**1. Coverage is structurally incomplete.** The NIFC history layer
aggregates federal agencies plus CalFire — and CalFire is the *only*
non-federal source. Washington DNR fires on state and private land are not
systematically in there. The record also thins hard after 2019 despite the
layer claiming coverage through 2024. Absence of a fire in this dataset
does not mean a plot didn't burn.

**2. Coordinates are fuzzed.** FIA perturbs public plot locations up to
about a mile to protect landowner privacy. Plots near a perimeter edge can
land on the wrong side. Noise for megafires, where interior dominates;
a real misclassification source for small ones. One "Minor" fire plot
showed a biomass *gain* — almost certainly a plot that never burned.

**3. Fire size is not fire severity.** A 200,000-acre fire burns as a
mosaic — unburned islands, light-severity patches, crown-fire cores. Size
class is a crude proxy. Real severity work needs dNBR from MTBS, which
FRAP and NIFC perimeters don't carry.

---

## THE MAP

Five layers now, all toggleable in `wa_timber.qgz`.

Burn scars in ember orange. Burned plots graduated by mortality increase.
National forests, wilderness, parks and counties underneath.

The geography is unambiguous: **fire concentrates on the dry east side.**
The dense cluster is Okanogan and Chelan — Carlton Complex 2014, North Star
2015, Tripod 2006. A second knot around Yakima and Naches. The wet west
slope of the Cascades and the Olympics are nearly clean.

Which lands on the practical point, and it's the one worth carrying:

**Washington's most productive timber ground and its most fire-prone ground
are largely different places.** The high-biomass west side rarely burns.
The east side burns hard and carries far less wood per acre. Yesterday's
biomass map and today's fire map are near-inverses of each other.

---

## RUNNING TALLY

The warehouse now holds six domains:

| Domain | Rows | What |
|---|---|---|
| Lake chemistry | 1,417 | WQP grab samples, 13 alpine lakes |
| Streamflow (15-min) | ~138,000 | 7 gages, continuous telemetry |
| Daily flow | 163,566 | 14 gages, 1990–2026 |
| Stream geometry | 489 | LiDAR-derived, Nisqually |
| Forest inventory | 531,490 | WA FIA trees, 2001–2022 |
| Fire perimeters | 4,921 | NIFC history, Washington |

**~840,000 rows.** Cost so far: effectively nothing. The warehouse
suspends 60 seconds after you stop typing.

---

## THE RUNNING SCORE ON HYPOTHESES

Two days, six predictions, five dead:

1. Evening snowmelt peak → **wrong**, morning peak, riparian ET
2. Dam release schedule → **wrong**, no weekday pattern
3. Rim Fire natural experiment → **dead**, monitoring gap
4. Small basins are flashier → **dead**, one data point carrying it
5. Regulated reaches are flashy → **wrong**, reservoirs smooth flow
6. Biomass loss scales with fire size → **wrong variable**, mortality does

Plus two silent data bugs that produced plausible-looking wrong answers:
a `.0` suffix that blocked 157,871 joins without erroring, and a
mean-of-ratios that reported growth where there was destruction.

Every one of them got caught in minutes instead of shipping, because the
metrics were already modeled, already tested, and the next question was
one query away.

**You're not chasing the answer. You're building the thing that tells you
when you're wrong.**

*— end of fire chapter*
