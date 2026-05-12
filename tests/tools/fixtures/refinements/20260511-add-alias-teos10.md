---
target: src/skills/netcdf-inspect/references/aliases.md
operation: add_alias
confidence: high
evidence:
  - cycle-6 Phase A finding "TEOS-10 ocean vocabulary"
  - 2026-05-11 dogfood on ocn.hist.0001-02-01_00.00.00.nc
  - "ocean MPAS-Ocean Temperature variable uses standard_name=sea_water_conservative_temperature, units=degree_C"
---

## MPAS-Ocean (TEOS-10)

MPAS-Ocean (and Omega) ship TEOS-10 standard names rather than the
older "potential temperature" / "practical salinity" terminology.
The mesh-history pair separates geometry (mesh file) from data
(history file); both are needed for a plot.

| User says | Possible variable names | Notes |
|-----------|-------------------------|-------|
| SST, sea surface temperature, ocean temperature, T | `Temperature` | TEOS-10 conservative-temperature; `standard_name = sea_water_conservative_temperature`; units `degree_C`; surface = top vertical layer (`NVertLayers=0`) |
| salinity, S | `Salinity` | TEOS-10 absolute-salinity; `standard_name = sea_water_absolute_salinity`; units `g kg-1` |
