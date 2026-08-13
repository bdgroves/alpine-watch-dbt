{{
    config(
        materialized       = 'incremental',
        unique_key         = 'measurement_sk',
        incremental_strategy = 'merge',
        on_schema_change   = 'append_new_columns',
        cluster_by         = ['sample_date']
    )
}}

-- THE MODEL THAT MATTERS. Everything the job posting means by
-- "incremental/delta load patterns, watermarking, late-arriving data,
-- schema evolution, replayable backfills" is happening in this file.
--
--  * merge + unique_key  -> re-processing the same row updates instead of
--                           duplicating. The model is idempotent, so a
--                           backfill is just `dbt run` with no filter.
--  * lookback window     -> we deliberately re-read a few days PAST the
--                           high-water mark, because WQP publishes lab
--                           results weeks after the sample date. A naive
--                           `> max(watermark)` silently drops those.
--  * on_schema_change    -> new upstream columns get added rather than
--                           blowing up the run.

{% set lookback_days = 3 %}

with staged as (

    select * from {{ ref('stg_wqp_results') }}

    {% if is_incremental() %}

        -- Watermark, minus a deliberate overlap for late arrivals.
        -- The merge on measurement_sk cleans up the re-read rows.
        where _loaded_at > (
            select dateadd(day, -{{ lookback_days }}, max(_loaded_at))
            from {{ this }}
        )

    {% endif %}

),

joined as (

    select
        s.measurement_sk,
        s.lake_id,
        s.station_id,
        l.lake_name,
        l.mountain_range,
        s.sample_date,
        s.characteristic,
        s.result_value,
        s.unit_code,
        s.detection_condition,

        -- Non-detects are real observations, not missing data. Flag them
        -- so downstream analysis can include or exclude on purpose.
        (s.detection_condition is not null) as is_non_detect,

        s._loaded_at,
        s._batch_id

    from staged s
    -- inner join: the fact table is scoped to the curated watchlist
    inner join {{ ref('dim_lakes') }} l
        on s.lake_id = l.lake_id

)

select * from joined
