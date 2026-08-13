{% snapshot snap_monitoring_stations %}

{{
    config(
        target_schema = 'snapshots',
        unique_key    = 'station_id',
        strategy      = 'check',
        check_cols    = ['station_name', 'latitude', 'longitude', 'huc8'],
        invalidate_hard_deletes = True
    )
}}

-- SCD Type 2 on station metadata. The upstream source overwrites in place,
-- so without this we'd lose the fact that a station was ever relocated or
-- renamed. dbt maintains dbt_valid_from / dbt_valid_to for us.
--
-- 'check' strategy (not 'timestamp') because WQP gives us no reliable
-- updated_at on station records.

select
    payload:MonitoringLocationIdentifier::varchar as station_id,
    payload:MonitoringLocationName::varchar       as station_name,
    payload:LatitudeMeasure::float                as latitude,
    payload:LongitudeMeasure::float               as longitude,
    payload:HUCEightDigitCode::varchar            as huc8,
    payload:OrganizationIdentifier::varchar       as organization_id
from {{ source('bronze', 'wqp_stations_raw') }}

{% endsnapshot %}
