with gages as (
    select * from {{ ref('gages') }}
)

select
    gage_id,
    gage_name,
    river,
    mountain_range,
    state_code,
    role
from gages
