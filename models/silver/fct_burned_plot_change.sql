{{ config(materialized='table') }}

-- The natural experiment that streamflow couldn't support: FIA plots
-- measured BOTH before and after the same fire.
--
-- Unlike streamgages, which get decommissioned, FIA plots are revisited
-- on a fixed cycle regardless of what happens to them. A plot that
-- burned in 2014 and was remeasured in 2019 carries its own baseline.
--
-- Sample size is the thing to check here, not the effect size. If this
-- comes back with a handful of plots, it's a curiosity, not a finding.

with joined as (
    select * from {{ ref('fct_plot_fire_history') }}
),

-- Plots that have a measurement on each side of a given fire
paired as (
    select
        plot_number,
        fire_id,
        incident_name,
        fire_year,
        reported_acres,
        size_class,
        owner_group,
        elevation_band,

        max(case when measurement_timing = 'Pre-fire'
                 then measurement_year end)              as pre_year,
        max(case when measurement_timing = 'Post-fire'
                 then measurement_year end)              as post_year,

        max(case when measurement_timing = 'Pre-fire'
                 then live_biomass_tons_per_acre end)    as pre_live_biomass,
        max(case when measurement_timing = 'Post-fire'
                 then live_biomass_tons_per_acre end)    as post_live_biomass,

        max(case when measurement_timing = 'Pre-fire'
                 then pct_dead end)                      as pre_pct_dead,
        max(case when measurement_timing = 'Post-fire'
                 then pct_dead end)                      as post_pct_dead,

        max(case when measurement_timing = 'Pre-fire'
                 then live_trees end)                    as pre_live_trees,
        max(case when measurement_timing = 'Post-fire'
                 then live_trees end)                    as post_live_trees

    from joined
    group by 1, 2, 3, 4, 5, 6, 7, 8
)

select
    *,
    post_year - pre_year                            as remeasure_interval,
    round(post_live_biomass - pre_live_biomass, 2)  as biomass_change_tpa,
    round(post_pct_dead - pre_pct_dead, 1)          as pct_dead_change,
    post_live_trees - pre_live_trees                as live_tree_change,
    round(
        (post_live_biomass - pre_live_biomass)
        / nullif(pre_live_biomass, 0) * 100, 1
    )                                               as pct_biomass_change
from paired
where pre_year is not null
  and post_year is not null
