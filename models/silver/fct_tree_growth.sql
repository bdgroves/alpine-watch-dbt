{{ config(materialized='table') }}

-- Diameter growth between remeasurements of the SAME physical tree.
--
-- PREV_TRE_CN is the link: on a revisit, FIA records the control number
-- of that tree's prior measurement. Self-joining on it gives a matched
-- pair, and the difference in DIA over the interval is real measured
-- growth - not modeled, not estimated.
--
-- This is the closest thing in this project to what commercial
-- growth-and-yield modeling actually does. If this table comes back
-- nearly empty, PREV_TRE_CN is sparse in the public data and we're
-- limited to snapshot analysis.

with current_meas as (
    select * from {{ ref('fct_fia_tree') }}
    where previous_tree_cn is not null
      and statuscd = 1
      and diameter_in is not null
),

previous as (
    select
        tree_cn,
        diameter_in    as prev_diameter_in,
        height_ft      as prev_height_ft,
        inventory_year as prev_inventory_year
    from {{ ref('fct_fia_tree') }}
    where diameter_in is not null
)

select
    c.tree_cn,
    c.plot_cn,
    c.species_name,
    c.wood_type,
    c.elevation_band,
    c.owner_group,
    c.crown_class,

    p.prev_inventory_year,
    c.inventory_year,
    c.inventory_year - p.prev_inventory_year    as interval_years,

    p.prev_diameter_in,
    c.diameter_in,
    round(c.diameter_in - p.prev_diameter_in, 2) as diameter_growth_in,

    -- Annualized, the number foresters actually compare.
    round(
        (c.diameter_in - p.prev_diameter_in)
        / nullif(c.inventory_year - p.prev_inventory_year, 0), 3
    )                                            as annual_diameter_growth_in

from current_meas c
inner join previous p
    on c.previous_tree_cn = p.tree_cn
where c.inventory_year > p.prev_inventory_year
