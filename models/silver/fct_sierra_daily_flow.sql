{{
    config(
        materialized         = 'incremental',
        unique_key           = 'flow_sk',
        incremental_strategy = 'merge',
        on_schema_change     = 'append_new_columns',
        cluster_by           = ['flow_date']
    )
}}

-- Daily discharge fact, ~163K rows spanning 1990-2026.
--
-- The LAG here is the whole point of putting this in a warehouse rather
-- than a spreadsheet: day-over-day change per gage, computed without a
-- self-join, partitioned so one gage's series never bleeds into another's.

{% set lookback_days = 14 %}

with staged as (
    select * from {{ ref('stg_sierra_daily_flow') }}

    {% if is_incremental() %}
        where _loaded_at > (
            select dateadd(day, -{{ lookback_days }}, max(_loaded_at))
            from {{ this }}
        )
    {% endif %}
),

with_change as (
    select
        flow_sk,
        gage_id,
        flow_date,
        water_year,
        discharge_cfs,
        approval_status,

        lag(discharge_cfs) over (
            partition by gage_id order by flow_date
        ) as prev_discharge_cfs,

        discharge_cfs - lag(discharge_cfs) over (
            partition by gage_id order by flow_date
        ) as change_cfs,

        -- 7-day centered rolling mean smooths the daily noise.
        avg(discharge_cfs) over (
            partition by gage_id order by flow_date
            rows between 3 preceding and 3 following
        ) as rolling_7d_mean_cfs,

        _loaded_at,
        _batch_id
    from staged
)

select
    w.*,
    g.river_system,
    g.gage_name
from with_change w
inner join {{ ref('dim_sierra_gages') }} g
    on w.gage_id = g.gage_id
