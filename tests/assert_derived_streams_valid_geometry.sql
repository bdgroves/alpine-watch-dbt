select segment_id
from {{ ref("stg_derived_streams") }}
where not st_isvalid(geom)
