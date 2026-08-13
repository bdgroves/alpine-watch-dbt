-- Data quality test with real meaning: our ST_AREA calculation from the
-- NLDI polygon should roughly agree with USGS's own published drainage
-- area. Allow 25% - the two are derived differently and small basins
-- especially can differ - but an order-of-magnitude gap means the polygon
-- is wrong, or got loaded in the wrong CRS.
--
-- Passes when zero rows return.

select
    gage_id,
    gage_name,
    usgs_drainage_area_sqmi,
    basin_area_sqmi,
    abs(basin_area_sqmi - usgs_drainage_area_sqmi)
        / nullif(usgs_drainage_area_sqmi, 0) as pct_diff
from {{ ref('dim_sierra_gages') }}
where usgs_drainage_area_sqmi is not null
  and usgs_drainage_area_sqmi > 0
  and abs(basin_area_sqmi - usgs_drainage_area_sqmi)
      / usgs_drainage_area_sqmi > 0.25
