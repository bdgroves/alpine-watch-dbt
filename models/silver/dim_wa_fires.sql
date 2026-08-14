{{ config(materialized='table') }}

with fires as (
    select * from {{ ref('stg_wa_fires') }}
)

select
    object_id                               as fire_id,
    incident_name,
    fire_year,
    gis_acres                               as reported_acres,
    computed_acres,
    agency,
    data_source,
    fire_geom,

    case
        when gis_acres >= 100000 then 'Megafire (100k+ ac)'
        when gis_acres >=  10000 then 'Large (10k-100k ac)'
        when gis_acres >=   1000 then 'Moderate (1k-10k ac)'
        when gis_acres >=    100 then 'Small (100-1k ac)'
        else 'Minor (<100 ac)'
    end                                     as size_class,

    -- Decade grouping, useful for trend work
    floor(fire_year / 10) * 10              as decade

from fires
