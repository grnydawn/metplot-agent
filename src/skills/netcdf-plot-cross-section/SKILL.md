---
name: netcdf-plot-cross-section
description: Generate a 2D cross-section plot (distance × depth or distance × pressure) along a chosen line through an unstructured-mesh NetCDF dataset. Handles great-circle sampling, nearest-cell lookup per sample, and pcolormesh rendering with depth-down axis convention. Use whenever the user asks for "a section from A to B", "lon vs depth", "lat vs depth", "transect", "Atlantic meridional section", or any 2D vertical-vs-distance view of an unstructured-grid variable.
---

# netcdf-plot-cross-section

## When to use

The user wants a 2D vertical-vs-distance slice through a 3D
unstructured field. Cues:

- "transect from (lat₁, lon₁) to (lat₂, lon₂)"
- "Atlantic meridional section", "Pacific zonal section"
- "lat × depth", "lon × depth", "great-circle slice"
- "Temperature along this line"

If the request is a map (one variable at one level) → use
`netcdf-plot-map`.
If the request is a single profile at one point →
`netcdf-plot-profile`.
If the request is time-on-x → `netcdf-plot-timeseries`.

## Quick reference

1. **Confirm inspection.** Inspect history + mesh together so you
   have `n_cells`, vertical-dim size, and the mesh convention.
2. **Sample the great circle.** Call
   `netcdf-reader.slice_along_section(mesh_path, lat1, lon1,
   lat2, lon2, n_samples)` → returns `cell_indices`,
   `distances_km`, `coords`.
   - `n_samples`: 60-200 is usually enough; more = smoother but
     slower. Each sample is one nearest-cell lookup.
3. **Fetch the data.** Call `netcdf-reader.read_slice(path,
   variable, time="first" or your time pick,
   cell_indices=cell_indices, mesh_path=mesh)`. The result
   shape is `(n_samples, n_levels)` (in on-disk dim order, which
   for MPAS-Ocean / Omega is `(NCells, NVertLayers)`).
4. **Build the vertical-coord array.** Read it from
   `read_slice(mesh, "refZMid", ...)` for MPAS-Ocean depth, or
   from `lev`/`plev` for atmospheric variables. If unavailable,
   pass `np.arange(n_levels)` as a fallback (the axis label will
   be "layer index").
5. **Call** `plot-renderer.render_section({values, distances_km,
   vertical_coord, vertical_units, title, units})`.
   - `vertical_units` ∈ {`m`, `depth_m`, `Pa`, `hPa`} triggers
     y-axis inversion (top of plot = sea surface or atmosphere
     top).
6. **Verify and report.** PNG file size > 10 KB; oracle's
   `drawn.distance_km_total` ≈ what you'd expect for the
   transect.

## Pitfalls

- **Endpoints in mesh's lon convention.** MPAS / Omega meshes
  are usually 0..360; a North Atlantic section is `lon1=280,
  lon2=350`, not `-80, -10`. Check `inspect()` →
  `spatial.lon_convention` first.
- **Degenerate endpoints.** `(lat1, lon1) == (lat2, lon2)` →
  `invalid_spec` error. Pick distinct points.
- **n_samples too small.** Coarse sampling (< 20) can skip whole
  features. Default to 60+ for any meaningful transect.
- **Sampling on a coarse mesh.** If `n_samples` exceeds
  `n_cells_along_path`, multiple samples will pick the same
  cell. That's fine — `render_section` just paints a wider
  visual band for that cell. Not a bug.
- **Vertical-coord units mismatch.** If the user says "depth"
  but the file ships pressure, the y-axis inversion default
  may flip wrong-way. Always check `vertical_units`.
- **Time-animation is out of scope.** Single time step per
  render. Loop externally if you need multiple frames.

## Verification

- `oracle.drawn.n_samples` == requested
- `oracle.drawn.distance_km_total` is physically sensible
  (10° lat span ≈ 1110 km; 90° lon at equator ≈ 10000 km)
- `oracle.drawn.invert_vertical` matches your `vertical_units`
  expectation

## See also

- `netcdf-inspect` — must run first
- `netcdf-plot-profile` — single-point vertical
- `netcdf-plot-map` — horizontal slice
- `netcdf-reader.slice_along_section` — the sampler
- `plot-renderer.render_section` — the pcolormesh renderer
