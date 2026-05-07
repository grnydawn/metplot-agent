# Common region bounding boxes

Used by `netcdf-plot-map` to resolve named regions in user requests.
Format: `lon_min, lon_max, lat_min, lat_max` in -180..180 convention.
The plot-renderer MCP shifts to 0..360 if the file uses that convention.

## Oceanic basins

| Name                | lon_min | lon_max | lat_min | lat_max |
|---------------------|---------|---------|---------|---------|
| North Atlantic      |     -80 |       0 |      20 |      70 |
| Tropical Atlantic   |     -60 |      20 |     -20 |      20 |
| South Atlantic      |     -70 |      20 |     -60 |       0 |
| North Pacific       |     120 |    -100 |      20 |      65 |
| Tropical Pacific    |     120 |     -70 |     -20 |      20 |
| Niño 3.4            |    -170 |    -120 |      -5 |       5 |
| South Pacific       |     150 |     -70 |     -60 |       0 |
| Indian Ocean        |      30 |     120 |     -40 |      30 |
| Southern Ocean      |    -180 |     180 |     -75 |     -40 |
| Arctic              |    -180 |     180 |      60 |      90 |

## Continental / land regions

| Name                | lon_min | lon_max | lat_min | lat_max |
|---------------------|---------|---------|---------|---------|
| CONUS               |    -125 |     -65 |      24 |      50 |
| Western US          |    -125 |    -100 |      30 |      50 |
| Eastern US          |    -100 |     -65 |      24 |      48 |
| Europe              |     -15 |      45 |      35 |      72 |
| Mediterranean       |     -10 |      40 |      30 |      48 |
| West Africa         |     -20 |      30 |      -5 |      25 |
| East Africa         |      30 |      55 |     -10 |      20 |
| South Asia          |      65 |     100 |       5 |      40 |
| East Asia           |     100 |     150 |      20 |      55 |
| Australia           |     110 |     155 |     -45 |     -10 |
| Amazon basin        |     -80 |     -45 |     -20 |       5 |

## Climate-relevant regions

| Name                | lon_min | lon_max | lat_min | lat_max | Note |
|---------------------|---------|---------|---------|---------|------|
| Tropics             |    -180 |     180 |     -30 |      30 | "tropics" by default = 30S–30N |
| Inner Tropics       |    -180 |     180 |     -23 |      23 | strict tropics, 23.5° |
| NH extratropics     |    -180 |     180 |      30 |      90 |      |
| SH extratropics     |    -180 |     180 |     -90 |     -30 |      |
| NH polar            |    -180 |     180 |      60 |      90 |      |
| SH polar            |    -180 |     180 |     -90 |     -60 |      |

## Hurricane / TC basins

| Name                | lon_min | lon_max | lat_min | lat_max |
|---------------------|---------|---------|---------|---------|
| North Atlantic TC   |    -100 |       0 |       0 |      45 |
| Eastern Pacific TC  |    -180 |     -75 |       0 |      35 |
| Western Pacific TC  |     100 |     180 |       0 |      45 |
| North Indian TC     |      40 |     100 |       0 |      30 |
| South Indian TC     |      30 |     120 |     -35 |       0 |
| South Pacific TC    |     135 |    -120 |     -35 |       0 |

## Adding regions

Append to the appropriate section. If the region crosses the dateline
(e.g. "North Pacific"), `lon_min` may be greater than `lon_max`; the
plot-renderer handles this.

<!-- REFINER_INSERT_BELOW -->
<!-- New regions from skill-refiner are appended below this marker. -->

<!-- REFINER_INSERT_ABOVE -->
