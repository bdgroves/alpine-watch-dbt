-- Conformed lake dimension. lake_id is the join key everywhere downstream --
-- ALPINE-WATCH assigns lake identity by which bounding-box query returned
-- a record, not by any station ID in the data itself.

with lakes as (
    select * from {{ ref('lakes') }}
)

select
    lake_id,
    lake_name,
    mountain_range,
    state_code,
    elevation_ft,
    latitude,
    longitude
from lakes
