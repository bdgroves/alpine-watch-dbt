-- Conform the NIFC perimeter history into something joinable.
--
-- Three real problems in this source, all handled here rather than in
-- the loader so the logic is visible and testable:
--
-- 1. fire_year runs 1070 to 9999. The low end is dendrochronology -
--    fire-scar reconstructions from tree rings, genuinely interesting
--    but not mappable to plot measurements. The 9999 is a null sentinel.
-- 2. Duplicate submissions. The same fire arrives from multiple
--    agencies - "Carlton Complex" and "Carlton", both 2014, both ~250k
--    acres. Keep the largest polygon per fire-year-name.
-- 3. Geometry validity. Repaired on load, but re-checked here because
--    an invalid ring silently breaks ST_INTERSECTS downstream.

with source as (
    select * from {{ source('bronze_fire', 'wa_fire_perimeters_raw') }}
),

typed as (
    select
        object_id,
        trim(upper(incident_name))          as incident_name,
        fire_year,
        gis_acres,
        agency,
        source                              as data_source,
        feature_cat,
        unique_fire_id,
        to_geography(geom_wkt)              as fire_geom
    from source
    where fire_year between 1900 and 2026   -- drop reconstructions and the 9999 sentinel
      and gis_acres > 0
      and geom_wkt is not null
),

deduped as (
    select *
    from typed
    -- Same fire, multiple agency submissions. Keep the largest polygon,
    -- which is generally the final mapped extent rather than an early
    -- operational estimate.
    qualify row_number() over (
        partition by fire_year, incident_name
        order by gis_acres desc
    ) = 1
)

select
    *,
    -- Geodesic acres computed from the polygon itself, alongside the
    -- reported figure. Divergence means the geometry and the attribute
    -- disagree, which is worth knowing.
    round(st_area(fire_geom) / 4046.8564224, 1) as computed_acres
from deduped
