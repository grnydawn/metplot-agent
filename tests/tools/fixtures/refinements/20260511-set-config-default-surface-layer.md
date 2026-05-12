---
target: src/skills/netcdf-plot-map/SKILL.md
operation: set_config_default
key: surface_layer_default
value: top
confidence: high
evidence:
  - cycle-6 Phase A finding "TEOS-10 ocean vocabulary"
  - "users asking for 'surface SST' on MPAS-Ocean files with NVertLayers axis expect the top vertical layer"
---

When a user asks for "surface X" / "SST" / "surface temperature" on
a file with an MPAS-style vertical layer dim (`NVertLayers`,
`nVertLevels`), default to the top layer rather than a 3-D plot
that errors out. Users explicitly want the surface slice unless
they ask for "depth-averaged" or "at depth N".
