{{
    config(
        materialized = 'table',
        cluster_by   = ['inventory_year', 'species_code']
    )
}}

-- The fact table. 531K trees joined to their plot and species.
--
-- Clustered on inventory_year + species_code because nearly every
-- question here filters or groups on one or both. At half a million
-- rows this is the first table in the project where clustering is
-- worth thinking about rather than decorative.

with trees as (
    select * from {{ ref('stg_fia_tree') }}
),

plots as (
    select * from {{ ref('dim_fia_plot') }}
),

species as (
    select * from {{ ref('dim_fia_species') }}
)

select
    t.tree_cn,
    t.plot_cn,
    t.previous_tree_cn,
    t.inventory_year,

    t.tree_status,
    t.statuscd,
    s.species_code,
    s.common_name                       as species_name,
    s.scientific_name,
    s.wood_type,

    t.diameter_in,
    t.height_ft,
    t.total_age_years,
    t.crown_class,
    t.trees_per_acre,
    t.carbon_above_ground_lb,
    t.dry_biomass_above_ground_lb,

    -- Diameter classes, 5-inch bins - the standard way foresters
    -- summarize stand structure.
    case
        when t.diameter_in <  5  then '1-5 in'
        when t.diameter_in < 10  then '5-10 in'
        when t.diameter_in < 15  then '10-15 in'
        when t.diameter_in < 20  then '15-20 in'
        when t.diameter_in < 30  then '20-30 in'
        when t.diameter_in < 40  then '30-40 in'
        else '40+ in'
    end                                 as diameter_class,

    p.elevation_ft,
    p.elevation_band,
    p.owner_group,
    p.forest_type_code,
    p.stand_age_years,
    p.plot_geom

from trees t
inner join plots p on t.plot_cn = p.plot_cn
left  join species s on t.species_code = s.species_code
