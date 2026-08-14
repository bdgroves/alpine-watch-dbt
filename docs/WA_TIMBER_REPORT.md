# Washington Timberland: What 531,490 Trees Say About How Forests Are Managed

**An analysis built on USDA Forest Inventory and Analysis data**
Brooks Groves · August 2026

---

## Why this exists

In April 2026, Weyerhaeuser's CEO told the Wall Street Journal the company
is building a tree-by-tree digital twin of 11 million acres — satellite
imagery, drone photography and lidar feeding a database that knows the
size, species and spacing of every stem it owns. The stated goal is to
roughly double 2025 profits by 2030 without lumber prices rising.

Four months later they posted a Data Engineer role: Azure Data Factory
into Snowflake into dbt, with geospatial ETL called out explicitly.

This analysis is what that job's output looks like at small scale. It uses
the public federal inventory — the same ground truth a commercial digital
twin has to be validated against — and asks the questions a timberland
owner actually asks.

---

## What was built

```
USDA FIA DataMart (CSV)
      │
      ▼
BRONZE   3 typed tables: 23,099 plots · 30,486 conditions · 531,490 trees
      │
      ▼
STAGING  typed, decoded, conformed
      │
      ▼
SILVER   dim_fia_plot (GEOGRAPHY) · dim_fia_species · fct_fia_tree
      │
      ▼
MARTS    plot timber profile · species mortality · stand structure
         · measured growth (157,871 remeasured tree pairs)
      │
      ▼
QGIS     6,157 mapped plots, statewide
```

Stack: Snowflake, dbt, Terraform-provisioned infrastructure, Python
loaders, QGIS for cartography. 73 automated data tests.

**One design decision worth stating:** this data landed as *typed columns*,
not `VARIANT`. The other feeds in this warehouse arrive as JSON from APIs
whose schemas we don't control, so `VARIANT` earns its keep there. FIA
arrives as CSV against a documented, stable schema. Choosing correctly cut
531,490 rows and 198 columns down to 9.6 MB of columnar storage.

---

## Finding 1 — Two philosophies of forestry, visible in one column

Average per acre, by who owns the land:

| Owner | Plots | Live biomass (t/ac) | Dead (t/ac) | % biomass dead | Sawtimber stems |
|---|---|---|---|---|---|
| Other federal | 427 | **146.9** | 14.8 | 9.2% | 18.7 |
| State & local | 1,267 | 92.2 | 8.1 | 8.1% | 11.4 |
| Forest Service | 7,283 | 91.3 | 12.8 | **12.3%** | 12.2 |
| Private | 3,830 | **54.6** | 4.6 | **7.8%** | 7.0 |

Other federal land — national parks, largely — carries **2.7× the standing
biomass per acre of private land**. Not because it grows better. Because
nothing has ever been removed.

The stand-age distribution makes the mechanism explicit: 1,942 Forest
Service plots are old growth (150+ years) against **107 on private land**.
Industrial timberland never reaches that age. It's harvested at 40–50 and
replanted.

Neither column is "better." They're different objectives — one optimizing
merchantable yield per acre per year, the other not optimizing yield at all.

---

## Finding 2 — Mortality looks different by stem than by volume

Counting stems, mortality is comparable across ownerships (private 24.8%,
Forest Service 28.4%). Counting *wood*, the gap widens sharply:

- Private: **4.6** dead tons/acre
- Forest Service: **12.8** dead tons/acre

Nearly threefold, on similar stem-count mortality. The difference is size.
Trees that die on managed land die small, early in a rotation. Trees that
die on federal land are large and old, and each snag is a great deal more
wood.

For a timber company this is the number that matters: **volume lost before
it can be harvested**. Managing on rotation converts standing mortality
risk into product.

---

## Finding 3 — A century-old pathogen, reproduced from a GROUP BY

Dead-tree share by species, minimum 200 stems:

| Species | Elevation band | Trees | % dead |
|---|---|---|---|
| **whitebark pine** | Subalpine | 2,440 | **57.9%** |
| **western white pine** | Upper montane | 1,466 | **45.2%** |
| lodgepole pine | Subalpine | 17,177 | 45.0% |
| Engelmann spruce | Subalpine | 5,787 | 40.9% |
| subalpine fir | Subalpine | 19,224 | 32.9% |

The top two are not a coincidence: both are five-needle white pines, both
highly susceptible to white pine blister rust — an introduced Eurasian
fungus that has been working through North American *Pinus strobus*
relatives for over a century. Add mountain pine beetle and fire suppression
and you get 58% mortality.

Whitebark pine is federally listed as threatened. This dataset independently
reproduces the reason why.

At genus scale the pattern holds: *Pinus* 33.9% dead across 60,265 trees,
against *Abies* 21.7% and *Pseudotsuga* 21.3%. And the bottom of the list
is equally consistent with the biology — *Thuja* (western redcedar) 14.2%,
*Chamaecyparis* (Alaska yellow-cedar) 11.8%, *Taxus* (Pacific yew) 11.5%.
Rot-resistant, long-lived, and they stand.

**The commercially reassuring number:** *Pseudotsuga* — Douglas-fir, the
foundation of the regional industry, 161,839 trees here — sits at 21.3%,
right at the state average. Boring. Weyerhaeuser's business model depends
on it staying boring.

---

## Finding 4 — Measured growth, and a finding that needs a caveat

From 157,871 matched remeasurement pairs — the same identified tree,
measured twice, actual diameter increment. Not modeled. Measured.

| Species | Elevation | Owner | Trees | Annual growth (in) |
|---|---|---|---|---|
| noble fir | Upper montane | Forest Service | 252 | 0.273 |
| Sitka spruce | Lowland | Private | 250 | 0.272 |
| **Douglas-fir** | **Lowland** | **Private** | **5,044** | **0.263** |
| western redcedar | Lowland | Private | 625 | 0.248 |
| Douglas-fir | Montane | Private | 3,381 | 0.243 |
| Douglas-fir | Lowland | State & local | 1,531 | 0.211 |
| Douglas-fir | Lowland | Other federal | 204 | 0.190 |
| Douglas-fir | Montane | Forest Service | 2,268 | 0.186 |

Douglas-fir on lowland private ground grows **0.263 inches of diameter per
year** — squarely inside the 0.15–0.30 range published for productive PNW
sites, which is how we know the pipeline is producing real forestry values
rather than plausible-looking noise.

**The caveat matters here.** Private land shows faster growth than federal
at the same species and elevation, consistently. At least four explanations
fit and this analysis separates none of them:

1. **Site selection.** Industrial timberland was acquired for productivity
   a century ago. The best ground went first; federal holdings are
   disproportionately what was left — steeper, higher, rockier.
2. **Silviculture.** Thinning, fertilization, genetically improved stock.
3. **Stand structure.** Younger managed stands put on diameter faster.
4. **Density.** Federal stands are frequently overstocked from decades of
   fire suppression; individual trees compete harder for light and water.

Elevation band is a crude control. The honest statement is: *the pattern is
real and consistent; the cause is not isolated by this analysis.*

Noble fir on Forest Service land topping the table is a useful check
against the simple story.

---

## The maps

Two views of the same 6,157 plots, rendered in QGIS from a Snowflake query.

**Standing biomass** traces Washington's forest geography exactly: a dense
high-value band down the west slope of the Cascades and into the Olympics,
falling off sharply across the crest into the drier northeast. The blank
center is the Columbia Basin — shrub-steppe, no trees, no plots.

**Mortality** tells a different story from the same points. The dark
clusters sit in the northeast corner and along the east slope — dry country,
beetle-prone lodgepole and ponderosa. The wet west-side band carrying the
highest biomass is mostly pale.

High-biomass forest is largely healthy forest. The wood that's dying is
where trees were already stressed.

---

## What this does not show

- **Coordinates are fuzzed.** FIA perturbs public plot locations up to
  roughly a mile to protect landowner privacy. Valid for regional pattern
  analysis; invalid for anything parcel-level.
- **"Private" is not "industrial."** The category includes family
  woodlots and small holdings alongside corporate timberland. The
  managed-rotation signal is almost certainly diluted.
- **No causal claims.** Ownership comparisons are observational.
- **One state, one snapshot.** Washington, inventory years 2001–2022.

---

## What it demonstrates

Against the Weyerhaeuser Data Engineer posting, this exercise covers:
Snowflake loading patterns and cost-aware warehouse design; dbt
materializations, incremental strategy and 73 automated tests; geospatial
handling from `GEOGRAPHY` types through cartographic output; Terraform
provisioning; and Python ingestion against government APIs and bulk files.

More to the point, it demonstrates the thing that actually matters: the
tests caught real problems. A float conversion silently appended `.0` to
157,871 join keys and returned zero rows instead of erroring. Species
codes for unidentified snags contaminated a mortality ranking at 100%
dead. Neither would have surfaced in a notebook. Both surfaced here
because a downstream model returned something a person who knows forests
could see was wrong.

That's the argument for building it this way.

---

*Data: USDA Forest Service, Forest Inventory and Analysis Database,
Washington, retrieved August 2026. Analysis and modeling by the author.*
