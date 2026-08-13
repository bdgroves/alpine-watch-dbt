with source as (
    select * from {{ source('bronze', 'streamflow_continuous_raw') }}
),

renamed as (
    select
        payload:gage_id::varchar                  as gage_id,
        payload:parameter_code::varchar           as parameter_code,
        payload:unit::varchar                     as unit,
        payload:datetime_utc::timestamp_ntz        as reading_ts,
        payload:value::float                       as reading_value,
        payload:qualifier::varchar                 as qualifier,
        _loaded_at,
        _batch_id
    from source
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key([
            'gage_id', 'parameter_code', 'reading_ts'
        ]) }} as reading_sk,
        *
    from renamed
    where gage_id is not null
      and reading_ts is not null

    qualify row_number() over (
        partition by reading_sk
        order by _loaded_at
    ) = 1
)

select * from final
