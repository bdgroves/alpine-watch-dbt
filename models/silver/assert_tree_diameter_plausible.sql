-- The scoping run reported a 152-inch diameter tree. That's 12.7 feet
-- across - plausible for old-growth western redcedar in Washington, but
-- extreme enough to be worth an explicit check rather than quiet trust.
--
-- 200 inches would be larger than any tree known in North America.
-- Anything past that is a data error, not a big tree.
--
-- Passes when zero rows return.

select
    tree_cn,
    species_name,
    diameter_in,
    height_ft,
    elevation_ft
from {{ ref('fct_fia_tree') }}
where diameter_in > 200
   or diameter_in < 0
   or height_ft > 400          -- taller than the tallest coast redwood
