{{
    config(
        materialized         = "incremental",
        unique_key           = "reading_sk",
        incremental_strategy = "merge",
        on_schema_change     = "append_new_columns",
        cluster_by            = ["reading_ts"]
    )
}}

{% set lookback_days = 7 %}

with staged as (
    select * from {{ ref("stg_streamflow") }}

    {% if is_incremental() %}
        where _loaded_at > (
            select dateadd(day, -{{ lookback_days }}, max(_loaded_at))
            from {{ this }}
        )
    {% endif %}
),

joined as (
    select
        s.reading_sk,
        s.gage_id,
        g.gage_name,
        g.river,
        g.mountain_range,
        g.role,
        s.parameter_code,
        s.unit,
        s.reading_ts,
        s.reading_value,
        s.qualifier,
        s._loaded_at,
        s._batch_id
    from staged s
    inner join {{ ref("dim_gages") }} g
        on s.gage_id = g.gage_id
)

select * from joined
