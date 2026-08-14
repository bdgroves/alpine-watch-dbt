-- Condition grain: a plot splits into multiple conditions when it
-- straddles a boundary - forest meets clearcut, or ownership changes,
-- or forest type changes. Trees belong to a CONDITION, not just a plot.
-- CONDPROP_UNADJ is the fraction of the plot this condition covers.

with source as (
    select * from {{ source('bronze_fia', 'fia_wa_cond_raw') }}
)

select
    cn                                  as cond_cn,
    plt_cn                              as plot_cn,
    condid                              as condition_id,
    invyr                               as inventory_year,

    cond_status_cd,
    case cond_status_cd
        when 1 then 'Forest'
        when 2 then 'Nonforest'
        when 3 then 'Water'
        when 4 then 'Census water'
        when 5 then 'Nonsampled'
        else 'Unknown'
    end                                 as condition_status,

    fortypcd                            as forest_type_code,
    stdage                              as stand_age_years,

    owncd                               as owner_code,
    owngrpcd                            as owner_group_code,
    -- OWNGRPCD is a small, stable, documented set - worth decoding.
    case owngrpcd
        when 10 then 'Forest Service'
        when 20 then 'Other federal'
        when 30 then 'State and local government'
        when 40 then 'Private'
        else 'Unknown'
    end                                 as owner_group,

    siteclcd                            as site_class_code,
    slope                               as slope_pct,
    aspect                              as aspect_deg,
    condprop_unadj                      as condition_proportion

from source
