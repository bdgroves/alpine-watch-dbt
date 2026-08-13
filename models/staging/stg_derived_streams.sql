with source as (
    select * from {{ source("bronze_lidar", "derived_streams_raw") }}
),

casted as (
    select
        segment_id,
        stream_type,
        network,
        to_geography(geom_wkt) as geom
    from source
)

select * from casted
