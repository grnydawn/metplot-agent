# Variable aliases

When the user names a quantity informally, look here first to map it to the
actual variable name in the current file. Multiple aliases may map to the
same canonical name; multiple files may use different canonical names for
the same physical quantity.

> This file is updated by the `skill-refiner` loop. New aliases discovered
> during sessions get proposed here as draft refinements; accepted ones
> merge in.

## Sea surface temperature

| User says        | Possible variable names                  | Notes                  |
|------------------|------------------------------------------|------------------------|
| SST              | `sst`, `tos`, `analysed_sst`, `SSTK`     | `tos` in CMIP, `sst` in NOAA OISST |
| sea temperature  | same                                     |                        |
| ocean surface temp | same                                   |                        |

Units: usually K in CMIP, °C in OISST, sometimes both in one file.

## 2-meter air temperature

| User says            | Possible variable names              | Notes |
|----------------------|--------------------------------------|-------|
| 2m temperature, T2m  | `tas`, `t2m`, `T2`, `temperature_2m` | `tas` in CMIP, `t2m` in ERA5, `T2` in WRF |
| surface air temp     | same                                 |       |
| screen temperature   | same                                 |       |

## Precipitation

| User says        | Possible variable names                | Notes |
|------------------|----------------------------------------|-------|
| precipitation, precip, rain | `pr`, `tp`, `precip`, `RAINNC` | `pr` in CMIP (kg m⁻² s⁻¹), `tp` in ERA5 (m), `RAINNC` in WRF (mm accumulated) |

⚠️ Precip variables differ in *both* units and *integration* (instantaneous
flux vs accumulated total). Always check units and time-integration before
plotting comparisons.

## Sea level pressure

| User says        | Possible variable names              | Notes |
|------------------|--------------------------------------|-------|
| MSLP, sea level pressure | `psl`, `msl`, `slp`, `PSL` | usually Pa |

## Geopotential height

| User says        | Possible variable names         | Notes |
|------------------|---------------------------------|-------|
| Z500, 500hPa height | `zg`, `z`, `gh`              | watch for geopotential vs geopotential height (factor of g) |

## Wind components

| User says        | Possible variable names              | Notes |
|------------------|--------------------------------------|-------|
| zonal wind, U    | `ua`, `u`, `U`, `eastward_wind`      | may be on staggered grid in WRF |
| meridional wind, V | `va`, `v`, `V`, `northward_wind`   | staggered separately from U |
| wind speed       | (compute from U, V)                  | usually not stored directly |

## Specific humidity / water vapor

| User says        | Possible variable names              | Notes |
|------------------|--------------------------------------|-------|
| humidity, q, specific humidity | `hus`, `q`, `QVAPOR`, `huss` | dimensionless (kg/kg) |
| relative humidity | `hur`, `rh`, `RH`                   | percent |
| total precipitable water | `prw`, `tcwv`, `pwv`         |       |

## Dataset-specific quirks

These accumulate from real session corrections:

<!-- REFINER_INSERT_BELOW -->
<!-- New entries from skill-refiner are appended below this marker. -->

<!-- REFINER_INSERT_ABOVE -->

## Adding entries manually

Format: a short table row under the appropriate physical-quantity section,
or a new section if the quantity isn't listed. Include the canonical name,
common file conventions, and any unit/integration gotchas.
