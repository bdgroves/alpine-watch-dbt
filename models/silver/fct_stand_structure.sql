{{ config(materialized='table') }}

-- Diameter distribution by owner group and elevation band.
--
-- Shape is the signal here. A natural uneven-aged stand shows many small
-- stems tapering smoothly to a few large ones - a reverse-J curve. An
-- even-aged plantation shows a bulge at whatever size class it was last
-- thinned to. Comparing private industrial land against Forest Service
-- land on the same axis should make different management regimes visible
-- without anyone labelling them.

with live as (
    select * from {{ ref('fct_fia_tree') }}
    where statuscd = 1
      and diameter_in is not null
)

select
    owner_group,
    elevation_band,
    diameter_class,

    count(*)                            as tree_count,
    round(sum(trees_per_acre), 1)       as expanded_trees_per_acre,
    round(avg(diameter_in), 1)          as avg_diameter_in,
    round(avg(height_ft), 1)            as avg_height_ft,
    round(sum(dry_biomass_above_ground_lb) / 2000.0, 1) as biomass_tons,

    -- Share of stems within this owner/elevation combination.
    round(
        count(*) * 100.0
        / sum(count(*)) over (partition by owner_group, elevation_band), 1
    )                                   as pct_of_stems

from live
where owner_group is not null
group by 1, 2, 3
