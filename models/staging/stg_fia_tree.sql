-- Tree grain: one row per tree per measurement.
--
-- Units are US customary throughout FIA: DIA in inches (diameter at
-- breast height, 4.5 ft), HT in feet, biomass and carbon in POUNDS.
-- TPA_UNADJ is the expansion factor - how many trees per acre this one
-- record represents. Any per-acre estimate must multiply by it.

with source as (
    select * from {{ source('bronze_fia', 'fia_wa_tree_raw') }}
)

select
    cn                                  as tree_cn,
    plt_cn                              as plot_cn,
    replace(prev_tre_cn, '.0', '')    as previous_tree_cn,
    condid                              as condition_id,
    invyr                               as inventory_year,

    statuscd,
    case statuscd
        when 0 then 'No status'
        when 1 then 'Live'
        when 2 then 'Dead'
        when 3 then 'Removed'
        else 'Unknown'
    end                                 as tree_status,

    spcd                                as species_code,
    dia                                 as diameter_in,
    ht                                  as height_ft,
    actualht                            as actual_height_ft,
    totage                              as total_age_years,
    tpa_unadj                           as trees_per_acre,
    carbon_ag                           as carbon_above_ground_lb,
    drybio_ag                           as dry_biomass_above_ground_lb,

    cclcd                               as crown_class_code,
    case cclcd
        when 1 then 'Open grown'
        when 2 then 'Dominant'
        when 3 then 'Co-dominant'
        when 4 then 'Intermediate'
        when 5 then 'Overtopped'
    end                                 as crown_class

from source
