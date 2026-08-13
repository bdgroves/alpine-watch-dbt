-- Flatten daily discharge from VARIANT, and derive the WATER YEAR.
--
-- Water year is a real hydrology convention, not an arbitrary choice:
-- Oct 1 - Sep 30, named for the calendar year it ENDS in. It exists so
-- a winter snowpack and the following spring melt land in the same
-- accounting year instead of being split across a January boundary.

with source as (
    select * from {{ source('bronze_sandbox', 'sierra_daily_flow_raw') }}
),

renamed as (
    select
        payload:gage_id::varchar          as gage_id,
        payload:flow_date::date           as flow_date,
        payload:discharge_cfs::float      as discharge_cfs,
        payload:approval::varchar         as approval_status,
        _loaded_at,
        _batch_id
    from source
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key(['gage_id', 'flow_date']) }} as flow_sk,

        gage_id,
        flow_date,
        discharge_cfs,
        approval_status,

        case
            when month(flow_date) >= 10 then year(flow_date) + 1
            else year(flow_date)
        end as water_year,

        _loaded_at,
        _batch_id
    from renamed
    where gage_id is not null
      and flow_date is not null

    qualify row_number() over (
        partition by flow_sk order by _loaded_at desc
    ) = 1
)

select * from final
