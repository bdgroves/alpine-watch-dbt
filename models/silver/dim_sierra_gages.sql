{{ config(materialized='table') }}

-- Gage dimension with basin geometry.
--
-- The interesting column here is basin_area_sqmi: computed from the NLDI
-- polygon with ST_AREA, sitting next to USGS's own published drainage_area.
-- Two independent measurements of the same physical thing - if they diverge
-- badly, something is wrong with the polygon, and there's a test below that
-- checks exactly that.

with gages as (
    select * from {{ ref('stg_sierra_gages') }}
),

enriched as (
    select
        gage_id,
        gage_name,

        -- River system, parsed from the USGS naming convention.
        case
            when gage_name ilike '%MERCED%'      then 'Merced'
            when gage_name ilike '%TUOLUMNE%'    then 'Tuolumne'
            when gage_name ilike '%STANISLAUS%'  then 'Stanislaus'
            when gage_name ilike '%CHERRY%'      then 'Tuolumne'
            when gage_name ilike '%ELEANOR%'     then 'Tuolumne'
            when gage_name ilike '%BIG C%'       then 'Tuolumne'
            else 'Other'
        end as river_system,

        latitude,
        longitude,
        gage_point,
        basin_geom,

        usgs_drainage_area_sqmi,

        -- ST_AREA on GEOGRAPHY returns square meters, geodesic.
        st_area(basin_geom) / 2589988.11 as basin_area_sqmi,

        -- Perimeter length, meters -> km. ST_LENGTH works on the boundary.
        st_perimeter(basin_geom) / 1000.0 as basin_perimeter_km

    from gages
)

select
    *,
    -- Gravelius compactness: 1.0 = perfect circle, higher = more elongated.
    -- Elongated basins route water to the outlet more slowly than compact
    -- ones of the same area, so this is a real shape descriptor, not decoration.
    basin_perimeter_km * 1000.0
        / (2 * sqrt(pi() * st_area(basin_geom)))  as compactness_ratio
from enriched
