{{ config(materialized='table') }}

with species as (
    select * from {{ ref('fia_species') }}
)

select
    spcd                                as species_code,
    common_name,
    genus,
    species                             as species_epithet,
    genus || ' ' || species             as scientific_name,
    species_symbol,
    case sftwd_hrdwd
        when 'S' then 'Softwood'
        when 'H' then 'Hardwood'
    end                                 as wood_type
from species
