-- Validates the LiDAR-derived stream network against the real, surveyed
-- USGS gage location - same accuracy-assessment technique Weyerhaeuser's
-- own water-mapping team uses for exactly this kind of derived layer.
--
-- Nisqually gage coordinates are hardcoded and verified directly from
-- the USGS station page (waterdata.usgs.gov/nwis/uv?site_no=12082500),
-- not estimated - 46.7528, -122.0825.
--
-- ST_DISTANCE on GEOGRAPHY returns geodesic meters natively - no manual
-- degrees-to-meters conversion needed here, unlike the QGIS join earlier.

with gage as (
    select
        '12082500' as gage_id,
        'Nisqually River near National, WA' as gage_name,
        st_makepoint(-122.0825, 46.7528) as geom
),

streams as (
    select * from {{ ref('stg_derived_streams') }}
),

distances as (
    select
        gage.gage_id,
        gage.gage_name,
        streams.segment_id,
        streams.stream_type,
        st_distance(gage.geom, streams.geom) as distance_m
    from gage
    cross join streams
)

select *
from distances
qualify row_number() over (partition by gage_id order by distance_m asc) = 1
