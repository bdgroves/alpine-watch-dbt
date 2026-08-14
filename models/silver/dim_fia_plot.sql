{{ config(materialized='table') }}

-- Plot dimension. Joined to its dominant condition so forest type,
-- ownership and stand age travel with the plot - most plots are a
-- single condition, and where they aren't we take the largest by area
-- proportion rather than silently multiplying rows.

with plots as (
    select * from {{ ref('stg_fia_plot') }}
),

conds as (
    select * from {{ ref('stg_fia_cond') }}
),

dominant_cond as (
    select *
    from conds
    qualify row_number() over (
        partition by plot_cn
        order by condition_proportion desc nulls last, condition_id
    ) = 1
)

select
    p.plot_cn,
    p.plot_number,
    p.countycd,
    p.inventory_year,
    p.measurement_year,
    p.plot_status,
    p.latitude,
    p.longitude,
    p.elevation_ft,
    p.plot_geom,

    c.condition_status,
    c.forest_type_code,
    c.stand_age_years,
    c.owner_group,
    c.slope_pct,
    c.aspect_deg,

    -- Elevation bands, roughly matching Cascade forest zones.
    case
        when p.elevation_ft <  1000 then 'Lowland (<1000 ft)'
        when p.elevation_ft <  3000 then 'Montane (1000-3000 ft)'
        when p.elevation_ft <  5000 then 'Upper montane (3000-5000 ft)'
        else 'Subalpine (>5000 ft)'
    end                                 as elevation_band

from plots p
left join dominant_cond c
    on p.plot_cn = c.plot_cn
