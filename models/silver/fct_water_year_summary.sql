{{ config(materialized='table') }}

-- One row per gage per water year. This is where the daily grain gets
-- rolled up into metrics hydrologists actually use.
--
-- Richards-Baker Flashiness Index:
--     sum(|Q_t - Q_t-1|) / sum(Q_t)
-- How "jumpy" a river is. Near 0 = smooth, spring-fed or heavily
-- reservoir-buffered. Higher = flashy, responding sharply to storms.
-- Dam-controlled reaches often score oddly because the jumps are
-- operational rather than hydrologic - which is itself visible here.

with daily as (
    select * from {{ ref('fct_sierra_daily_flow') }}
),

summarized as (
    select
        gage_id,
        gage_name,
        river_system,
        water_year,

        count(*)                          as days_of_record,
        round(avg(discharge_cfs), 1)      as mean_cfs,
        round(min(discharge_cfs), 1)      as min_cfs,
        round(max(discharge_cfs), 1)      as max_cfs,
        round(median(discharge_cfs), 1)   as median_cfs,

        -- Percentiles: p10 is a low-flow/drought indicator, p90 high-flow.
        round(percentile_cont(0.10) within group (order by discharge_cfs), 1) as p10_cfs,
        round(percentile_cont(0.90) within group (order by discharge_cfs), 1) as p90_cfs,

        sum(abs(change_cfs))              as sum_abs_change,
        sum(discharge_cfs)                as sum_discharge,

        -- Total volume: cfs * 86400 s/day / 43560 cu ft per acre-foot
        round(sum(discharge_cfs) * 86400.0 / 43560.0, 0) as annual_volume_af

    from daily
    group by 1, 2, 3, 4
)

select
    *,
    case
        when sum_discharge > 0
        then round(sum_abs_change / sum_discharge, 4)
    end as rb_flashiness_index,

    -- Rank each gage's water years by volume - drought vs. wet year context.
    rank() over (
        partition by gage_id order by annual_volume_af desc
    ) as wettest_year_rank
from summarized
where days_of_record >= 300  -- drop partial years at record boundaries
