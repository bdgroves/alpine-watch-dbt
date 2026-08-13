-- Conformed lake dimension. Sourced from a seed because the 13-lake
-- watchlist is a curated editorial decision, not upstream data.

with lakes as (

    select * from {{ ref('lakes') }}

)

select
    station_id,
    lake_name,
    state_code,
    mountain_range,
    latitude,
    longitude,
    elevation_ft
from lakes
