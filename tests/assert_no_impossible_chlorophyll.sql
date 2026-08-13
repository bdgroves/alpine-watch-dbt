-- Singular test: a business rule that no generic test expresses.
-- Chlorophyll-a can't be negative, and anything over 500 ug/L in an
-- alpine lake is a units error upstream, not a bloom.
--
-- A singular test passes when it returns ZERO rows.

select
    measurement_sk,
    station_id,
    sample_date,
    result_value,
    unit_code
from {{ ref('fct_lake_measurements') }}
where characteristic ilike '%chlorophyll%'
  and (
        result_value < 0
     or result_value > 500
  )
