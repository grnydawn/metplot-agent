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
    adapter: FormatAdapter,
    ssh_config: dict[str, Any] | None = None,
    mesh_path: str | None = None,
) -> dict[str, Any]:
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
            # MPAS-family files use NVertLayers (history) / nVertLevels
            # (mesh); recognized case-insensitively.
            v_dim_set_lower = {"plev", "lev", "level", "altitude", "z",
                                "bottom_top", "s_rho", "s_w",
                                "nvertlayers", "nvertlevels"}
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

        # Compute slice shape and bytes estimate
        shape: list[int] = []
        for d in da.dims:
            if d in ("time", "Time", "ocean_time") and "time_index" in resolved:
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
