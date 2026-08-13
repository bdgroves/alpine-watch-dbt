-- Flatten raw VARIANT into typed columns. No business logic here:
-- cast, rename, and drop obvious garbage. Nothing else.

with source as (

    select * from {{ source('bronze', 'wqp_results_raw') }}

),

renamed as (

    select
        payload:MonitoringLocationIdentifier::varchar         as station_id,
        payload:ActivityStartDate::date                       as sample_date,
        payload:CharacteristicName::varchar                   as characteristic,

        -- WQP ships numbers as strings and sometimes ships "*Non-detect".
        -- try_to_double returns NULL instead of failing the whole load.
        try_to_double(payload:ResultMeasureValue::varchar)     as result_value,

        -- Slash in the key means it needs quoting in the path expression.
        payload:"ResultMeasure/MeasureUnitCode"::varchar       as unit_code,
        payload:ResultDetectionConditionText::varchar          as detection_condition,

        _loaded_at,
        _batch_id

    from source

),

final as (

    select
        -- Deterministic surrogate key: the same natural grain always hashes
        -- the same, which is what makes the incremental merge idempotent.
        {{ dbt_utils.generate_surrogate_key([
            'station_id', 'sample_date', 'characteristic', 'unit_code'
        ]) }} as measurement_sk,

        *
    from renamed
    where station_id is not null
      and sample_date is not null

)

select * from final
