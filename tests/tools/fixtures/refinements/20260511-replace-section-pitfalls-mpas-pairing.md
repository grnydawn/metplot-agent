---
target: src/skills/netcdf-inspect/SKILL.md
section: Pitfalls
operation: replace_section
confidence: high
evidence:
  - cycle-6 Phase A finding "MPAS files come in pairs"
  - cycle-6 Phase A finding "Restart files silently accepted as plot input"
  - cycle-6 Phase A finding "Dual-grid files"
  - 2026-05-11 dogfood on cice.nc, eamxx.nc, ocn.hist.*.nc, ocean_mesh.nc
---

- **MPAS mesh-history pairing.** MPAS-family files (MPAS-Ocean,
  MPAS-Atmosphere, MPAS-Seaice, Omega, E3SM) split geometry from
  data. A history file (`*.hist.<date>.nc`) ships `Temperature` /
  `Salinity` but no `lat`/`lon`; the matching mesh file
  (`ocean_mesh.nc` / `*_mesh.nc` / `init.nc`) ships `latCell` /
  `lonCell` / `verticesOnCell`. To plot any field, both are needed
  — surface the pairing when only one is supplied.
- **Restart files are not history files.** Files with
  `product: model-restart` (EAMxx) or no metadata + flattened
  layout (`nj=1, ni=N`, CICE) are not designed for plotting; their
  spatial layout is for resume, not display. Surface this to the
  user and steer toward the matching history file.
- **Dual-grid files.** EAMxx / SCREAM restarts carry two unrelated
  spatial grids in one file: physics columns (`ncol`) and dycore
  spectral-element (`elem × gp × gp`). Default user-facing plots
  to the physics grid; surface dycore-state variables under a
  separate "dynamics state (advanced)" heading.
