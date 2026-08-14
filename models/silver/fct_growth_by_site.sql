{{ config(materialized='table') }}

-- Site productivity: how fast does wood actually accumulate, by species
-- and site condition? This is the core input to timberland valuation -
-- an acre that grows 0.30 in/yr is worth materially more than one that
-- grows 0.10, all else equal.
--
-- Built from MEASURED remeasurement pairs, not a growth model. Every row
-- behind this is one identified tree measured twice.

with growth as (
    select * from {{ ref('fct_tree_growth') }}
    where interval_years between 5 and 15   -- normal FIA remeasure cycle
      and diameter_growth_in between -1 and 15  -- drop implausible values
)

select
    species_name,
    wood_type,
    elevation_band,
    owner_group,
    crown_class,

    count(*)                                        as remeasured_trees,
    round(avg(annual_diameter_growth_in), 4)        as mean_annual_growth_in,
    round(median(annual_diameter_growth_in), 4)     as median_annual_growth_in,
    round(percentile_cont(0.90) within group (order by annual_diameter_growth_in), 4)
                                                    as p90_annual_growth_in,
    round(avg(interval_years), 1)                   as mean_interval_years,
    round(avg(prev_diameter_in), 1)                 as mean_starting_diameter_in

from growth
group by 1, 2, 3, 4, 5
having count(*) >= 50
