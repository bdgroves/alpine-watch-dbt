{{ config(materialized='table') }}

-- Plot-level timber assessment. One row per FIA plot visit, built to
-- answer the questions a timberland owner actually asks:
--   Where is the merchantable wood, who owns it, and what's at risk?
--
-- Key FIA mechanic: TPA_UNADJ is the expansion factor. Each tree record
-- represents N trees per acre. Any per-acre estimate MUST multiply by it,
-- or you're reporting raw tally counts and the numbers are meaningless.
--
-- Biomass and carbon arrive in POUNDS per tree; /2000 converts to tons.

with trees as (
    select * from {{ ref('fct_fia_tree') }}
    where statuscd in (1, 2)
),

plot_agg as (
    select
        plot_cn,

        count(*)                                            as trees_tallied,
        sum(case when statuscd = 1 then 1 else 0 end)       as live_trees,
        sum(case when statuscd = 2 then 1 else 0 end)       as dead_trees,
        round(sum(case when statuscd = 2 then 1 else 0 end) * 100.0
              / nullif(count(*), 0), 1)                     as pct_dead,

        -- Per-acre estimates, live trees only (dead wood isn't merchantable)
        round(sum(case when statuscd = 1
                  then dry_biomass_above_ground_lb * trees_per_acre end)
              / 2000.0, 2)                                  as live_biomass_tons_per_acre,
        round(sum(case when statuscd = 1
                  then carbon_above_ground_lb * trees_per_acre end)
              / 2000.0, 2)                                  as live_carbon_tons_per_acre,

        -- Dead biomass = salvage opportunity, and a fuel-load signal
        round(sum(case when statuscd = 2
                  then dry_biomass_above_ground_lb * trees_per_acre end)
              / 2000.0, 2)                                  as dead_biomass_tons_per_acre,

        round(avg(case when statuscd = 1 then diameter_in end), 1)
                                                            as avg_live_diameter_in,
        round(max(case when statuscd = 1 then diameter_in end), 1)
                                                            as max_live_diameter_in,
        round(avg(case when statuscd = 1 then height_ft end), 1)
                                                            as avg_live_height_ft,

        -- Sawtimber-size stems: >= 12 in is roughly the commercial
        -- threshold for conifer sawlogs in the PNW.
        sum(case when statuscd = 1 and diameter_in >= 12 then 1 else 0 end)
                                                            as sawtimber_stems,

        mode(case when statuscd = 1 then species_name end)  as dominant_species

    from trees
    group by 1
)

select
    p.plot_cn,
    p.plot_number,
    p.inventory_year,
    p.measurement_year,
    p.latitude,
    p.longitude,
    p.plot_geom,
    p.elevation_ft,
    p.elevation_band,
    p.owner_group,
    p.forest_type_code,
    p.stand_age_years,
    p.slope_pct,

    a.trees_tallied,
    a.live_trees,
    a.dead_trees,
    a.pct_dead,
    a.live_biomass_tons_per_acre,
    a.live_carbon_tons_per_acre,
    a.dead_biomass_tons_per_acre,
    a.avg_live_diameter_in,
    a.max_live_diameter_in,
    a.avg_live_height_ft,
    a.sawtimber_stems,
    a.dominant_species,

    -- Rotation-stage bucketing. PNW industrial Douglas-fir rotations run
    -- roughly 35-50 years; federal land is managed on much longer or no
    -- rotation at all. These buckets describe the stand, not a policy.
    case
        when p.stand_age_years is null   then 'Unknown'
        when p.stand_age_years <  20     then 'Regeneration (<20 yr)'
        when p.stand_age_years <  40     then 'Young (20-40 yr)'
        when p.stand_age_years <  80     then 'Mature (40-80 yr)'
        when p.stand_age_years < 150     then 'Late (80-150 yr)'
        else 'Old growth (150+ yr)'
    end                                                     as stand_stage

from {{ ref('dim_fia_plot') }} p
inner join plot_agg a on p.plot_cn = a.plot_cn
where p.condition_status = 'Forest'
