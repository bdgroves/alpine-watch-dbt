{{ config(materialized='table') }}

-- The spatial join: which FIA plots fall inside which fire perimeters.
--
-- 12,807 plot visits crossed against 1,788 fire polygons. Snowflake
-- handles the cross product internally - ST_INTERSECTS on GEOGRAPHY is
-- indexed, so this is not the brute-force 23M-comparison job it looks
-- like on paper.
--
-- Sign convention on years_since_fire:
--   positive = plot measured AFTER the fire (post-fire condition)
--   negative = plot measured BEFORE the fire (pre-fire baseline)
-- Both are useful, and having both for the same plot is the whole point.
--
-- COVERAGE CAVEAT: this perimeter source aggregates federal agencies
-- plus CalFire. Washington DNR fires on state and private land are not
-- systematically included, and the record thins sharply after 2019.
-- Absence of a fire here does NOT mean a plot did not burn.

with plots as (
    select
        plot_cn,
        plot_number,
        measurement_year,
        inventory_year,
        plot_geom,
        owner_group,
        elevation_band,
        live_biomass_tons_per_acre,
        dead_biomass_tons_per_acre,
        pct_dead,
        live_trees,
        dead_trees,
        stand_age_years,
        dominant_species
    from {{ ref('fct_plot_timber_profile') }}
),

fires as (
    select
        fire_id,
        incident_name,
        fire_year,
        reported_acres,
        size_class,
        fire_geom
    from {{ ref('dim_wa_fires') }}
    where fire_year >= 1980   -- older perimeters predate any live plot record
)

select
    p.plot_cn,
    p.plot_number,
    p.measurement_year,
    p.owner_group,
    p.elevation_band,
    p.dominant_species,
    p.stand_age_years,

    f.fire_id,
    f.incident_name,
    f.fire_year,
    f.reported_acres,
    f.size_class,

    p.measurement_year - f.fire_year        as years_since_fire,
    case
        when p.measurement_year > f.fire_year then 'Post-fire'
        when p.measurement_year < f.fire_year then 'Pre-fire'
        else 'Same year'
    end                                     as measurement_timing,

    p.live_biomass_tons_per_acre,
    p.dead_biomass_tons_per_acre,
    p.pct_dead,
    p.live_trees,
    p.dead_trees

from plots p
inner join fires f
    on st_intersects(p.plot_geom, f.fire_geom)
