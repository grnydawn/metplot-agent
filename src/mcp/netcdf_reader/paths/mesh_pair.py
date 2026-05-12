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
  2. `init.nc` / `grid.nc` in the same dir (canonical MPAS / CICE
     initial-state / grid filenames).
  3. `*_mesh.nc` in the same dir (broad MPAS).
  4. `*mesh*.nc` in the same dir (broader — catches `ocean_mesh.nc`
     when the history file's stem shares no prefix with it).
  5. CICE grid families: `*_grid.nc`, `pop_grid*.nc`, `gx*v*.nc`.
  6. EAMxx physics-grid families: `*scrip*.nc`, `ne*pg2*.nc`,
     `ne*lonlat*.nc`.

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

    # 2. init.nc / grid.nc — canonical MPAS initial-state / CICE
    #    grid filenames in the same directory.
    add(parent / "init.nc")
    add(parent / "grid.nc")

    # 3. *_mesh.nc — anything ending in _mesh.nc (MPAS family).
    for p in sorted(parent.glob("*_mesh.nc")):
        add(p)

    # 4. *mesh*.nc — broader (e.g. ocean_mesh.nc, mesh_atm.nc).
    for p in sorted(parent.glob("*mesh*.nc")):
        add(p)

    # 5. CICE grid-file families.
    for pattern in ("*_grid.nc", "pop_grid*.nc", "gx*v*.nc"):
        for p in sorted(parent.glob(pattern)):
            add(p)

    # 6. EAMxx physics-grid families.
    for pattern in ("*scrip*.nc", "ne*pg2*.nc", "ne*lonlat*.nc"):
        for p in sorted(parent.glob(pattern)):
            add(p)

    # Cycle 10 Task B — F-03 dim-aware re-rank. When ≥2 candidates
    # compete, open each (cheap: dim sizes only) and promote
    # dim-matching meshes ahead of basename-only matches. The
    # basename-rank order is preserved within each group so the
    # exact-prefix heuristic still wins ties.
    if len(candidates) >= 2:
        candidates = _rank_by_dim_match(history_path, candidates)

    return candidates


def _rank_by_dim_match(history_path: Path,
                        candidates: list[Path]) -> list[Path]:
    """Open the history file once and each candidate once (metadata
    only), score each candidate by whether its dims agree with the
    history's via `validate_mesh_pair`, and return candidates with
    dim-matching ones first. Failure to open any file is non-fatal —
    that candidate falls to the bottom with no dim-match.
    """
    try:
        hist_ds = xr.open_dataset(history_path, decode_times=False)
    except Exception:
        return candidates  # can't even open history → leave order alone
    try:
        matches: list[Path] = []
        non_matches: list[Path] = []
        for c in candidates:
            try:
                cand_ds = xr.open_dataset(c, decode_times=False)
            except Exception:
                non_matches.append(c)
                continue
            try:
                err = validate_mesh_pair(hist_ds, cand_ds)
            except Exception:
                err = "validator exception"
            finally:
                cand_ds.close()
            if err is None:
                matches.append(c)
            else:
                non_matches.append(c)
        return matches + non_matches
    finally:
        hist_ds.close()


def validate_mesh_pair(history_ds: xr.Dataset,
                        mesh_ds: xr.Dataset) -> str | None:
    """Confirm a history file and a mesh/grid file share dimensions
    closely enough to be safely paired. Returns None on success,
    or a short human-readable error message on mismatch.

    Dispatch order (most-specific first):

      1. MPAS: if both files expose an MPAS cell dim (`nCells` /
         `NCells`, case-insensitive). Cycle-6 dogfooding showed
         history files use uppercase dim names while mesh files use
         lowercase; the comparison is case-insensitive.

      2. EAMxx: if both files expose an `ncol` dim (the EAMxx
         physics-column axis). Pair valid iff the sizes match.

      3. CICE: if both files expose `nj` AND `ni` dims. Pair valid
         iff `history.nj * history.ni == grid.nj * grid.ni` (the
         restart's horizontal axis is often flattened to (1, N)
         while the grid file ships the original (nj, ni) shape).

    Returns the first failure message it produces (so a clearly-MPAS
    file with an MPAS cell-dim mismatch reports MPAS, not CICE).
    """
    from src.mcp.netcdf_reader.conventions.mpas import (
        _MPAS_CELL_DIM_NAMES, _MPAS_EDGE_DIM_NAMES, _has_dim_ci,
    )

    # 1. MPAS path
    hist_cell = _has_dim_ci(history_ds, _MPAS_CELL_DIM_NAMES)
    mesh_cell = _has_dim_ci(mesh_ds, _MPAS_CELL_DIM_NAMES)
    if hist_cell is not None and mesh_cell is not None:
        hist_n = int(history_ds.sizes[hist_cell])
        mesh_n = int(mesh_ds.sizes[mesh_cell])
        if hist_n != mesh_n:
            return (f"cell-dim size mismatch: history.{hist_cell}={hist_n}, "
                    f"mesh.{mesh_cell}={mesh_n}")
        hist_edge = _has_dim_ci(history_ds, _MPAS_EDGE_DIM_NAMES)
        mesh_edge = _has_dim_ci(mesh_ds, _MPAS_EDGE_DIM_NAMES)
        if hist_edge and mesh_edge:
            hist_e = int(history_ds.sizes[hist_edge])
            mesh_e = int(mesh_ds.sizes[mesh_edge])
            if hist_e != mesh_e:
                return (f"edge-dim size mismatch: "
                        f"history.{hist_edge}={hist_e}, "
                        f"mesh.{mesh_edge}={mesh_e}")
        return None

    # 2. EAMxx physics path
    if "ncol" in history_ds.dims and "ncol" in mesh_ds.dims:
        hist_n = int(history_ds.sizes["ncol"])
        mesh_n = int(mesh_ds.sizes["ncol"])
        if hist_n != mesh_n:
            return (f"ncol size mismatch: history.ncol={hist_n}, "
                    f"grid.ncol={mesh_n}")
        return None

    # 3. CICE path
    if ("nj" in history_ds.dims and "ni" in history_ds.dims
            and "nj" in mesh_ds.dims and "ni" in mesh_ds.dims):
        h_nj = int(history_ds.sizes["nj"])
        h_ni = int(history_ds.sizes["ni"])
        g_nj = int(mesh_ds.sizes["nj"])
        g_ni = int(mesh_ds.sizes["ni"])
        if h_nj * h_ni != g_nj * g_ni:
            return (f"(nj*ni) product mismatch: "
                    f"history.nj*ni={h_nj * h_ni}, "
                    f"grid.nj*ni={g_nj * g_ni}")
        return None

    # Nothing recognizable — surface MPAS's classic message (the
    # most common pairing case).
    if hist_cell is None and "ncol" not in history_ds.dims:
        return ("history file has no recognizable unstructured cell "
                "dim (MPAS `nCells`/`NCells`, EAMxx `ncol`, "
                "or CICE `nj`+`ni`)")
    return ("mesh/grid file has no recognizable unstructured cell "
            "dim (MPAS `nCells`/`NCells`, EAMxx `ncol`, "
            "or CICE `nj`+`ni`)")
