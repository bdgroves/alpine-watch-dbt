-- Plot grain: one row per plot per inventory year (a plot VISIT).
-- Coordinates become GEOGRAPHY here so everything downstream can join
-- spatially against the gage basins already in this warehouse.
--
-- NOTE: FIA public coordinates are deliberately fuzzed - swapped or
-- perturbed up to ~1 mile to protect landowner privacy. Fine for
-- watershed-scale work, wrong for anything needing precise location.

with source as (
    select * from {{ source('bronze_fia', 'fia_wa_plot_raw') }}
)

select
    cn                                  as plot_cn,
    statecd,
    countycd,
    plot                                as plot_number,
    invyr                               as inventory_year,
    measyear                            as measurement_year,
    plot_status_cd,

    case plot_status_cd
        when 1 then 'Sampled - forest'
        when 2 then 'Sampled - nonforest'
        when 3 then 'Nonsampled'
        else 'Unknown'
    end                                 as plot_status,

    lat                                 as latitude,
    lon                                 as longitude,
    elev                                as elevation_ft,
    st_makepoint(lon, lat)              as plot_geom

from source
where lat is not null
  and lon is not null
