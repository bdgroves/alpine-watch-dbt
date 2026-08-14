{{ config(materialized='table') }}

-- Dead-tree share by species and elevation band. 21% of all measured
-- trees in Washington are standing dead - FIA counts snags deliberately,
-- they're real forest structure and real habitat.
--
-- Species with elevated mortality relative to the state average are
-- worth a second look: could be insect pressure, drought stress, or
-- simply a short-lived species. This model surfaces the question, it
-- doesn't answer it.

with trees as (
    select * from {{ ref('fct_fia_tree') }}
    where statuscd in (1, 2)   -- live or dead only; exclude removed/no-status
      and species_name is not null
      and species_name not ilike '%unknown%'
)

select
    species_name,
    wood_type,
    elevation_band,

    count(*)                                        as total_trees,
    sum(case when statuscd = 2 then 1 else 0 end)   as dead_trees,
    round(
        sum(case when statuscd = 2 then 1 else 0 end) * 100.0 / count(*), 1
    )                                               as pct_dead,

    round(avg(case when statuscd = 1 then diameter_in end), 1)
                                                    as avg_live_diameter_in,
    round(avg(case when statuscd = 2 then diameter_in end), 1)
                                                    as avg_dead_diameter_in

from trees
group by 1, 2, 3
having count(*) >= 200   -- drop thin cells where a percentage is noise
order by pct_dead desc
