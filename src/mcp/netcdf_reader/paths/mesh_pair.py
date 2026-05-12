"""MPAS-family mesh-history pairing heuristics.

MPAS-Ocean (and MPAS-A, MPAS-Seaice, Omega, E3SM) ships geometry
(`latCell`, `lonCell`, `verticesOnCell`) in a separate "mesh" file
from the time-varying data (`Temperature`, `Salinity`, …) in
"history" files. Plotting any field needs both — cycle 8 §3.3.

`find_mesh_candidates(history_path)` returns a ranked list of
likely mesh-file paths in the history file's directory. The caller
(`tools/inspect.py`) surfaces this list via a
`mesh_pairing_required` ambiguous envelope.

`validate_mesh_pair(history_ds, mesh_ds)` (cycle 8 §3.3, added with
Task 3) confirms a user-supplied mesh-file actually matches the
history's dimensions before opening the pair.

Ranking (high → low confidence):

  1. `<base-stem>_mesh.nc` in the same dir (e.g. `myrun_mesh.nc`
     for `myrun.hist.2024-01.nc`). Walks dotted-prefix components
     of the stem.
  2. `init.nc` in the same dir (canonical MPAS initial-state file).
  3. `*_mesh.nc` in the same dir (broad).
  4. `*mesh*.nc` in the same dir (broader — catches `ocean_mesh.nc`
     when the history file's stem shares no prefix with it).

Self is excluded from results.
"""
from __future__ import annotations

from pathlib import Path

import xarray as xr


def find_mesh_candidates(history_path: Path) -> list[Path]:
    history_path = Path(history_path)
    try:
        history_path = history_path.resolve()
    except OSError:
        return []
    parent = history_path.parent
    if not parent.is_dir():
        return []

    candidates: list[Path] = []
    seen: set[Path] = set()

    def add(p: Path) -> None:
        try:
            rp = p.resolve()
        except OSError:
            return
        if rp == history_path or rp in seen or not rp.is_file():
            return
        seen.add(rp)
        candidates.append(rp)

    stem = history_path.stem  # without ".nc"
    # Walk dotted-prefix components so e.g. "myrun.hist.2024-01"
    # tries: "myrun.hist.2024-01", "myrun.hist", "myrun".
    stem_prefixes: list[str] = [stem]
    if "." in stem:
        parts = stem.split(".")
        for i in range(len(parts) - 1, 0, -1):
            stem_prefixes.append(".".join(parts[:i]))

    # 1. Exact-prefix mesh match.
    for base in stem_prefixes:
        add(parent / f"{base}_mesh.nc")

    # 2. init.nc — canonical MPAS initial-state filename.
    add(parent / "init.nc")

    # 3. *_mesh.nc — anything ending in _mesh.nc.
    for p in sorted(parent.glob("*_mesh.nc")):
        add(p)

    # 4. *mesh*.nc — broader (e.g. ocean_mesh.nc, mesh_atm.nc).
    for p in sorted(parent.glob("*mesh*.nc")):
        add(p)

    return candidates


def validate_mesh_pair(history_ds: xr.Dataset,
                        mesh_ds: xr.Dataset) -> str | None:
    """Confirm a history file and a mesh file share dimensions
    closely enough to be safely paired. Returns None on success,
    or a short human-readable error message on mismatch.

    Cycle-6 dogfooding showed history files use uppercase MPAS dim
    names (`NCells`, `NEdges`, `NVertLayers`) while mesh files use
    lowercase (`nCells`, `nEdges`, `nVertLevels`). The comparison
    must be case-insensitive."""
    from src.mcp.netcdf_reader.conventions.mpas import (
        _MPAS_CELL_DIM_NAMES, _MPAS_EDGE_DIM_NAMES, _has_dim_ci,
    )
    hist_cell = _has_dim_ci(history_ds, _MPAS_CELL_DIM_NAMES)
    mesh_cell = _has_dim_ci(mesh_ds, _MPAS_CELL_DIM_NAMES)
    if hist_cell is None:
        return "history file has no MPAS cell dim (`nCells`/`NCells`)"
    if mesh_cell is None:
        return "mesh file has no MPAS cell dim (`nCells`/`NCells`)"
    hist_n = int(history_ds.sizes[hist_cell])
    mesh_n = int(mesh_ds.sizes[mesh_cell])
    if hist_n != mesh_n:
        return (f"cell-dim size mismatch: history.{hist_cell}={hist_n}, "
                f"mesh.{mesh_cell}={mesh_n}")
    # Edge dims are the second-strongest signal — only check if both
    # files declare one.
    hist_edge = _has_dim_ci(history_ds, _MPAS_EDGE_DIM_NAMES)
    mesh_edge = _has_dim_ci(mesh_ds, _MPAS_EDGE_DIM_NAMES)
    if hist_edge and mesh_edge:
        hist_e = int(history_ds.sizes[hist_edge])
        mesh_e = int(mesh_ds.sizes[mesh_edge])
        if hist_e != mesh_e:
            return (f"edge-dim size mismatch: history.{hist_edge}={hist_e}, "
                    f"mesh.{mesh_edge}={mesh_e}")
    return None
