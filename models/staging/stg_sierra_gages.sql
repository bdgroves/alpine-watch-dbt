-- Cast the NLDI basin polygon from WKT to native GEOGRAPHY.
-- Everything downstream can then use ST_ functions directly.

with source as (
    select * from {{ source('bronze_sandbox', 'sierra_gages_raw') }}
)

select
    gage_id,
    gage_name,
    latitude,
    longitude,
    drainage_area                        as usgs_drainage_area_sqmi,
    to_geography(basin_wkt)              as basin_geom,
    st_makepoint(longitude, latitude)    as gage_point
from source
