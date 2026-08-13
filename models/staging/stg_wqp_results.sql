with source as (
    select * from {{ source('bronze', 'wqp_results_raw') }}
),

renamed as (
    select
        payload:_alpine_lake_id::varchar                       as lake_id,
        payload:MonitoringLocationIdentifier::varchar           as station_id,
        payload:ActivityStartDate::date                         as sample_date,
        payload:CharacteristicName::varchar                     as characteristic,
        try_to_double(payload:ResultMeasureValue::varchar)      as result_value,

        coalesce(
            payload:"ResultMeasure/MeasureUnitCode"::varchar,
            payload:MeasureUnitCode::varchar
        )                                                       as unit_code,

        payload:ResultDetectionConditionText::varchar           as detection_condition,

        _loaded_at,
        _batch_id
    from source
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key([
            'lake_id', 'station_id', 'sample_date', 'characteristic', 'unit_code'
        ]) }} as measurement_sk,
        *
    from renamed
    where lake_id is not null
      and sample_date is not null
)

select * from final
qualify row_number() over (
    partition by measurement_sk
    order by _loaded_at
) = 1  -- WQP sends real duplicates (lab replicates, multi-org submissions) for the
       -- same station/date/characteristic/unit. Keep one, deterministically.
