# src/mcp/netcdf_reader/tools/resolve_spec.py
"""⤴ format-agnostic — eligible for _core/ lift.

resolve_spec() — validate and normalize a slice spec without reading
array values. Returns the spec the renderer (cycle 2) consumes.
"""
from __future__ import annotations

import difflib
from typing import TYPE_CHECKING, Any

import numpy as np

from src.mcp.netcdf_reader import envelope, selectors
from src.mcp.netcdf_reader.paths.classify import ClassifyError, classify

if TYPE_CHECKING:
    from src.mcp.netcdf_reader.protocols import FormatAdapter


def _close_matches(name: str, names: list[str], k: int = 3) -> list[str]:
    return difflib.get_close_matches(name, names, n=k, cutoff=0.0)


def resolve_spec(
    path: str,
    variable: str,
    *,
    time: Any = None,
    level: Any = None,
    lat: Any = None,
    lon: Any = None,
    region: str | None = None,
    regrid: str | None = None,
    cell_index: int | None = None,
    cell_indices: list[int] | None = None,
    index_selectors: dict[str, list[int]] | None = None,
    adapter: FormatAdapter,
    ssh_config: dict[str, Any] | None = None,
    mesh_path: str | None = None,
) -> dict[str, Any]:
    # Cycle 11 Task 2: cell-axis selectors are mutually exclusive
    # with lat/lon (the rectilinear/curvilinear path); rejecting at
    # the resolve layer surfaces a clean invalid_spec instead of a
    # confused isel.
    if (cell_index is not None or cell_indices is not None) and (
            lat is not None or lon is not None):
        return envelope.error(
            "invalid_spec",
            "cell_index/cell_indices are mutually exclusive with "
            "lat/lon selectors", context={"path": path})
    if cell_index is not None and cell_indices is not None:
        return envelope.error(
            "invalid_spec",
            "supply either cell_index or cell_indices, not both",
            context={"path": path})
    # Cycle 12 Task 1: index_selectors shape validation (cheap
    # checks before we open the file). Each entry must be a list
    # of 2 or 3 ints; stride (if given) must be >= 1.
    if index_selectors is not None:
        if not isinstance(index_selectors, dict):
            return envelope.error(
                "invalid_spec",
                "index_selectors must be a dict {dim_name: [start, "
                "stop, stride?]}",
                context={"path": path})
        for dname, spec in index_selectors.items():
            if not isinstance(spec, (list, tuple)) or len(spec) not in (2, 3):
                return envelope.error(
                    "invalid_spec",
                    f"index_selectors[{dname!r}] must be a list of "
                    f"2 or 3 ints [start, stop, stride?]; got {spec!r}",
                    context={"path": path, "dim": dname})
            try:
                _vals = [int(v) for v in spec]
            except (TypeError, ValueError):
                return envelope.error(
                    "invalid_spec",
                    f"index_selectors[{dname!r}] values must be ints; "
                    f"got {spec!r}",
                    context={"path": path, "dim": dname})
            if len(_vals) == 3 and _vals[2] < 1:
                return envelope.error(
                    "invalid_spec",
                    f"index_selectors[{dname!r}] stride must be >= 1; "
                    f"got {_vals[2]}",
                    context={"path": path, "dim": dname})
    try:
        cls = classify(path)
    except ClassifyError as e:
        return envelope.error(envelope.ErrorCode.FILE_NOT_FOUND, str(e),
                              context={"path": path})

    try:
        ds = adapter.open(cls.paths, ssh_config=ssh_config)
    except FileNotFoundError as e:
        return envelope.error(envelope.ErrorCode.FILE_NOT_FOUND, str(e),
                              context={"path": path})

    # Cycle 8 task 4: when paired with a mesh file, validate the
    # dim-match before doing any variable work. Mesh data isn't
    # needed at the spec-resolution layer (just sanity-check it
    # pairs cleanly with the history file).
    if mesh_path is not None:
        try:
            cls_mesh = classify(mesh_path)
        except ClassifyError as e:
            ds.close()
            return envelope.error(
                envelope.ErrorCode.FILE_NOT_FOUND, str(e),
                context={"mesh_path": mesh_path})
        try:
            mesh_ds = adapter.open(cls_mesh.paths or [mesh_path],
                                    ssh_config=ssh_config)
        except FileNotFoundError as e:
            ds.close()
            return envelope.error(
                envelope.ErrorCode.FILE_NOT_FOUND, str(e),
                context={"mesh_path": mesh_path})
        try:
            from src.mcp.netcdf_reader.paths.mesh_pair import (
                validate_mesh_pair,
            )
            err = validate_mesh_pair(ds, mesh_ds)
        finally:
            mesh_ds.close()
        if err:
            ds.close()
            return envelope.error(
                envelope.ErrorCode.MULTI_FILE_COMBINE_FAILED,
                f"history/mesh dim mismatch: {err}",
                context={"path": path, "mesh_path": mesh_path})

    try:
        if variable not in ds.data_vars:
            close = _close_matches(variable, [str(n) for n in ds.data_vars])
            return envelope.ambiguous(
                "variable",
                f"unknown variable: {variable!r}",
                candidates=[
                    {"value": c, "label": c,
                     "long_name": ds[c].attrs.get("long_name"),
                     "units": ds[c].attrs.get("units"),
                     "evidence": ["string-distance match"], "confidence": 0.5,
                     "param": "variable", "sensitive": False}
                    for c in close
                ] or [{"value": str(n), "label": str(n),
                       "long_name": ds[n].attrs.get("long_name"),
                       "units": ds[n].attrs.get("units"),
                       "evidence": [], "confidence": 0.1,
                       "param": "variable", "sensitive": False}
                      for n in list(ds.data_vars)[:5]],
                prompt=f"No variable named {variable!r}. Did you mean one of these?",
                retry_with_param="variable",
                context={"available": [str(n) for n in ds.data_vars]},
            )

        da = ds[variable]
        resolved: dict[str, Any] = {}
        notes: list[str] = []
        applied: list[dict[str, Any]] = []

        # --- time ---
        if time is not None:
            t_sel = selectors.parse_time(time)
            t_dim = next((d for d in da.dims if d in ("time", "Time", "ocean_time")), None)
            if t_dim is None:
                return envelope.error("internal_error",
                                      f"variable {variable} has no time dim", context={})
            tcoord = ds[t_dim].values
            if t_sel.kind == "iso":
                target = np.datetime64(t_sel.value)
                # Find exact or nearest
                if target in tcoord:
                    idx = int(np.where(tcoord == target)[0][0])
                    resolved["time_match"] = "exact"
                else:
                    diffs = np.abs(tcoord - target)
                    idx = int(np.argmin(diffs))
                    resolved["time_match"] = "nearest"
                resolved["time_index"] = idx
                resolved["time_value"] = str(tcoord[idx])
                notes.append(f"time matched {resolved['time_match']}")
            elif t_sel.kind == "sentinel":
                idx = 0 if t_sel.value == "first" else len(tcoord) - 1
                resolved["time_index"] = idx
                resolved["time_value"] = str(tcoord[idx])
                resolved["time_match"] = "exact"
            elif t_sel.kind == "index":
                resolved["time_index"] = t_sel.value
                resolved["time_value"] = str(tcoord[t_sel.value])
                resolved["time_match"] = "exact"

        # --- level ---
        if level is not None:
            # Vertical-dim names by family (recognized case-insensitively):
            #   CF / generic   : plev, lev, level, altitude, z
            #   WRF            : bottom_top
            #   ROMS           : s_rho, s_w
            #   MPAS           : nvertlayers, nvertlevels
            #   EAMxx          : lev (already covered), ilev (interface)
            #   CICE5/6        : nilyr (ice layers), nslyr (snow layers),
            #                    nkice, nkbio, ncat (thickness categories)
            v_dim_set_lower = {"plev", "lev", "level", "altitude", "z",
                                "bottom_top", "s_rho", "s_w",
                                "nvertlayers", "nvertlevels",
                                "ilev",
                                "nilyr", "nslyr", "nkice", "nkbio",
                                "ncat", "ntilyr", "ntslyr"}
            v_dim = next((d for d in da.dims
                          if str(d).lower() in v_dim_set_lower), None)
            if v_dim is None:
                return envelope.error(envelope.ErrorCode.NOT_4D,
                                      f"variable {variable} has no vertical dim",
                                      context={"dims": list(da.dims)})
            l_sel = selectors.parse_level(level)
            lcoord = ds[v_dim].values
            if l_sel.kind == "numeric":
                idx = int(np.argmin(np.abs(lcoord - l_sel.value)))
                resolved["level_index"] = idx
                resolved["level_value"] = float(lcoord[idx])
            elif l_sel.kind == "sentinel":
                # surface = lowest pressure-axis convention; for plev that's max
                if l_sel.value == "surface":
                    idx = int(np.argmax(lcoord)) if v_dim == "plev" else 0
                else:  # top
                    idx = int(np.argmin(lcoord)) if v_dim == "plev" else len(lcoord) - 1
                resolved["level_index"] = idx
                resolved["level_value"] = float(lcoord[idx])

        # --- lat/lon ---
        lat_dim = next((d for d in da.dims if d in ("lat", "latitude", "y")), None)
        lon_dim = next((d for d in da.dims if d in ("lon", "longitude", "x")), None)
        if lat is not None and lat_dim:
            lat_sel = selectors.parse_latlon(lat)
            lat_v = ds[lat_dim].values
            if lat_sel.kind == "bbox":
                lo, hi = lat_sel.value
                mask = (lat_v >= lo) & (lat_v <= hi)
                idxs = np.where(mask)[0]
                if len(idxs) == 0:
                    return envelope.error(envelope.ErrorCode.EMPTY_SLICE,
                                          f"no lat values in {lat_sel.value}",
                                          context={})
                resolved["lat_indices"] = [int(idxs[0]), int(idxs[-1])]
            elif lat_sel.kind == "point":
                idx = int(np.argmin(np.abs(lat_v - lat_sel.value)))
                resolved["lat_index"] = idx
        if lon is not None and lon_dim:
            lon_sel = selectors.parse_latlon(lon)
            lon_v = ds[lon_dim].values
            if lon_sel.kind == "bbox":
                lo, hi = lon_sel.value
                mask = (lon_v >= lo) & (lon_v <= hi)
                idxs = np.where(mask)[0]
                if len(idxs) == 0:
                    return envelope.error(envelope.ErrorCode.EMPTY_SLICE,
                                          f"no lon values in {lon_sel.value}",
                                          context={})
                resolved["lon_indices"] = [int(idxs[0]), int(idxs[-1])]
            elif lon_sel.kind == "point":
                idx = int(np.argmin(np.abs(lon_v - lon_sel.value)))
                resolved["lon_index"] = idx

        # --- cell-axis selectors (cycle 11) ---
        # Find the variable's cell dim (case-insensitive). MPAS
        # uses NCells (history) / nCells (mesh). Cycle 11 is
        # MPAS-only; CICE/EAMxx cell-axis selectors are cycle 12+.
        cell_dim = next((d for d in da.dims
                         if str(d).lower() == "ncells"), None)
        if cell_index is not None:
            if cell_dim is None:
                return envelope.error(
                    "invalid_spec",
                    f"variable {variable!r} has no cell dim (NCells); "
                    f"cell_index requires an unstructured cell axis",
                    context={"dims": list(da.dims)})
            n = int(ds.sizes[cell_dim])
            if not (0 <= cell_index < n):
                return envelope.error(
                    envelope.ErrorCode.OUT_OF_BOUNDS,
                    f"cell_index {cell_index} out of range for "
                    f"{cell_dim}={n}",
                    context={"cell_dim": cell_dim, "n_cells": n})
            resolved["cell_index"] = int(cell_index)
            resolved["cell_dim"] = cell_dim
        if cell_indices is not None:
            if cell_dim is None:
                return envelope.error(
                    "invalid_spec",
                    f"variable {variable!r} has no cell dim (NCells); "
                    f"cell_indices requires an unstructured cell axis",
                    context={"dims": list(da.dims)})
            n = int(ds.sizes[cell_dim])
            idx_arr = np.asarray(cell_indices, dtype=np.int64)
            if idx_arr.size == 0:
                return envelope.error(
                    envelope.ErrorCode.EMPTY_SLICE,
                    "cell_indices is empty",
                    context={"cell_dim": cell_dim})
            if (idx_arr.min() < 0) or (idx_arr.max() >= n):
                return envelope.error(
                    envelope.ErrorCode.OUT_OF_BOUNDS,
                    f"cell_indices out of range for {cell_dim}={n}",
                    context={"cell_dim": cell_dim, "n_cells": n,
                             "min": int(idx_arr.min()),
                             "max": int(idx_arr.max())})
            resolved["cell_indices"] = idx_arr.tolist()
            resolved["cell_dim"] = cell_dim

        # --- index_selectors (cycle 12: ncks -d parity) ---
        # Resolve dim names case-insensitively against da.dims and
        # check same-dim conflicts with named-axis selectors.
        if index_selectors:
            resolved_idx: dict[str, list[int]] = {}
            # Build a map of which named selector occupies each dim
            # of this variable (lower-cased dim name → kind).
            occupied: dict[str, str] = {}
            for d in da.dims:
                dl = str(d).lower()
                if d in ("time", "Time", "ocean_time") and (
                        "time_index" in resolved):
                    occupied[dl] = "time"
                if "level_index" in resolved and dl in {
                        "plev", "lev", "level", "altitude", "z",
                        "bottom_top", "s_rho", "s_w",
                        "nvertlayers", "nvertlevels", "ilev",
                        "nilyr", "nslyr", "nkice", "nkbio",
                        "ncat", "ntilyr", "ntslyr"}:
                    occupied[dl] = "level"
                if d in ("lat", "latitude", "y") and (
                        "lat_index" in resolved
                        or "lat_indices" in resolved):
                    occupied[dl] = "lat"
                if d in ("lon", "longitude", "x") and (
                        "lon_index" in resolved
                        or "lon_indices" in resolved):
                    occupied[dl] = "lon"
                if dl == "ncells" and (
                        "cell_index" in resolved
                        or "cell_indices" in resolved):
                    occupied[dl] = "cell"

            for dname, spec_vals in index_selectors.items():
                # Case-insensitive resolution against the variable's dims.
                actual = next((d for d in da.dims
                               if str(d).lower() == dname.lower()), None)
                if actual is None:
                    return envelope.error(
                        "invalid_spec",
                        f"index_selectors references dim {dname!r} which "
                        f"is not a dim of variable {variable!r}",
                        context={"dim": dname,
                                 "var_dims": [str(x) for x in da.dims]})
                if str(actual).lower() in occupied:
                    return envelope.error(
                        "invalid_spec",
                        f"index_selectors targets dim {actual!r} which is "
                        f"already constrained by {occupied[str(actual).lower()]!r} "
                        f"selector; pick one or the other",
                        context={"dim": str(actual),
                                 "other": occupied[str(actual).lower()]})
                vals = [int(v) for v in spec_vals]
                start = vals[0]
                stop = vals[1]
                stride = vals[2] if len(vals) == 3 else 1
                n = int(ds.sizes[actual])
                if not (0 <= start < n):
                    return envelope.error(
                        envelope.ErrorCode.OUT_OF_BOUNDS,
                        f"index_selectors[{actual!r}] start {start} out of "
                        f"range for dim size {n}",
                        context={"dim": str(actual), "size": n,
                                 "start": start})
                if not (start <= stop < n):
                    return envelope.error(
                        envelope.ErrorCode.OUT_OF_BOUNDS,
                        f"index_selectors[{actual!r}] stop {stop} out of "
                        f"range for dim size {n} (must satisfy "
                        f"start <= stop < {n})",
                        context={"dim": str(actual), "size": n,
                                 "start": start, "stop": stop})
                resolved_idx[str(actual)] = [start, stop, stride]
            resolved["index_selectors"] = resolved_idx

        # Compute slice shape and bytes estimate
        idx_sel = resolved.get("index_selectors") or {}
        shape: list[int] = []
        for d in da.dims:
            if str(d) in idx_sel:
                s, e, st = idx_sel[str(d)]
                # Inclusive-stop with stride: indices s, s+st, ..., last <= e
                shape.append((e - s) // st + 1)
            elif d in ("time", "Time", "ocean_time") and "time_index" in resolved:
                shape.append(1)
            elif d in ("plev", "lev", "level", "bottom_top") and "level_index" in resolved:
                shape.append(1)
            elif d in ("lat", "latitude", "y") and "lat_indices" in resolved:
                lo, hi = resolved["lat_indices"]
                shape.append(hi - lo + 1)
            elif d in ("lat", "latitude", "y") and "lat_index" in resolved:
                shape.append(1)
            elif d in ("lon", "longitude", "x") and "lon_indices" in resolved:
                lo, hi = resolved["lon_indices"]
                shape.append(hi - lo + 1)
            elif d in ("lon", "longitude", "x") and "lon_index" in resolved:
                shape.append(1)
            elif (str(d).lower() == "ncells"
                  and "cell_index" in resolved):
                # cell_index reduces the cell axis to a scalar.
                shape.append(1)
            elif (str(d).lower() == "ncells"
                  and "cell_indices" in resolved):
                shape.append(len(resolved["cell_indices"]))
            else:
                shape.append(int(ds.sizes[d]))

        itemsize = da.dtype.itemsize
        nbytes = itemsize
        for s in shape:
            nbytes *= s

        if regrid == "to_centers":
            applied.append({"kind": "regrid_to_centers"})

        spec = {
            "path": cls.raw,
            "variable": variable,
            "selectors": {
                "time": time, "level": level, "lat": lat, "lon": lon,
                "region": region, "regrid": regrid,
                "cell_index": cell_index,
                "cell_indices": cell_indices,
                "index_selectors": index_selectors,
            },
            "resolved": resolved,
            "slice_shape": shape,
            "estimated_bytes": int(nbytes),
            "applied_transforms": applied,
            "notes": notes,
        }
        return envelope.success(spec)
    finally:
        ds.close()
