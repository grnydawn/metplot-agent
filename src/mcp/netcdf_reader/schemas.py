# src/mcp/netcdf_reader/schemas.py
"""JSON Schema (`inputSchema`) definitions for every netcdf-reader tool.

Fixes the bug where tools were registered with the empty
`{"type": "object"}` shape (no `properties`), which left the agent
runtime unable to pass arguments through `dispatch(name, args)`.

Each entry mirrors the keyword signature of the underlying tool
function (see `server.dispatch`). `required` lists exactly the
parameters that have no default in the Python signature, so the
existing `TypeError` guard at `server.dispatch` still owns the
"missing required arg" path gracefully.
"""
from __future__ import annotations

from typing import Any

# Shared property fragments reused across several tools.
_PATH = {"type": "string", "description": "Path to the NetCDF (.nc) file."}
_VARIABLE = {"type": "string", "description": "Variable name within the file."}
_SSH_CONFIG = {
    "type": ["object", "null"],
    "description": "Optional remote-access (SSH) config for the file.",
}
_MESH_PATH = {
    "type": ["string", "null"],
    "description": "Optional path to a separate unstructured-mesh file.",
}
# Selector values may be a scalar or a [start, stop] pair; allow both.
_SELECTOR = {
    "description": "Coordinate selector: scalar value, label, or [min, max] range.",
}
_CONVENTION = {
    "type": "string",
    "description": "Mesh convention (e.g. 'mpas', 'ugrid'). Defaults to auto-detect.",
}


def _obj(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "inspect": _obj(
        {"path": _PATH, "ssh_config": _SSH_CONFIG, "mesh_path": _MESH_PATH},
        ["path"],
    ),
    "resolve_spec": _obj(
        {
            "path": _PATH,
            "variable": _VARIABLE,
            "time": _SELECTOR,
            "level": _SELECTOR,
            "lat": _SELECTOR,
            "lon": _SELECTOR,
            "region": {"type": ["string", "null"],
                       "description": "Named region for bbox selection."},
            "regrid": {"type": ["string", "null"],
                       "description": "Optional regrid target."},
            "cell_index": {"type": ["integer", "null"]},
            "cell_indices": {"type": ["array", "null"],
                             "items": {"type": "integer"}},
            "index_selectors": {"type": ["object", "null"]},
            "ssh_config": _SSH_CONFIG,
            "mesh_path": _MESH_PATH,
        },
        ["path", "variable"],
    ),
    "regrid_to_centers": _obj(
        {"spec": {"type": "object",
                  "description": "Resolved-spec dict to regrid to cell centers."}},
        ["spec"],
    ),
    "peek": _obj(
        {
            "path": _PATH,
            "variable": _VARIABLE,
            "time": _SELECTOR,
            "level": _SELECTOR,
            "lat": _SELECTOR,
            "lon": _SELECTOR,
            "ssh_config": _SSH_CONFIG,
        },
        ["path", "variable"],
    ),
    "read_slice": _obj(
        {
            "path": _PATH,
            "variable": _VARIABLE,
            "time": _SELECTOR,
            "level": _SELECTOR,
            "lat": _SELECTOR,
            "lon": _SELECTOR,
            "region": {"type": ["string", "null"]},
            "regrid": {"type": ["string", "null"]},
            "cell_index": {"type": ["integer", "null"]},
            "cell_indices": {"type": ["array", "null"],
                             "items": {"type": "integer"}},
            "index_selectors": {"type": ["object", "null"]},
            "max_inline_bytes": {"type": "integer",
                                 "description": "Max bytes to inline before spilling to disk."},
            "ssh_config": _SSH_CONFIG,
            "mesh_path": _MESH_PATH,
        },
        ["path", "variable"],
    ),
    "compute_stats": _obj(
        {
            "path": _PATH,
            "variable": _VARIABLE,
            "time": _SELECTOR,
            "level": _SELECTOR,
            "lat": _SELECTOR,
            "lon": _SELECTOR,
            "region": {"type": ["string", "null"]},
            "ssh_config": _SSH_CONFIG,
        },
        ["path", "variable"],
    ),
    "find_variables": _obj(
        {"path": _PATH,
         "hint": {"type": "string",
                  "description": "Search hint, e.g. 'temperature'."}},
        ["path", "hint"],
    ),
    "find_time": _obj(
        {"path": _PATH,
         "hint": {"type": "string",
                  "description": "Time search hint, e.g. a date or 'latest'."}},
        ["path", "hint"],
    ),
    "find_nearest_cell": _obj(
        {
            "mesh_path": {"type": "string",
                          "description": "Path to the unstructured-mesh file."},
            "lat": {"type": "number", "description": "Target latitude."},
            "lon": {"type": "number", "description": "Target longitude."},
            "convention": _CONVENTION,
        },
        ["mesh_path", "lat", "lon"],
    ),
    "cells_in_bbox": _obj(
        {
            "mesh_path": {"type": "string"},
            "lat_min": {"type": "number"},
            "lat_max": {"type": "number"},
            "lon_min": {"type": "number"},
            "lon_max": {"type": "number"},
            "convention": _CONVENTION,
        },
        ["mesh_path", "lat_min", "lat_max", "lon_min", "lon_max"],
    ),
    "reduce_variable": _obj(
        {
            "path": _PATH,
            "variable": _VARIABLE,
            "reduce_dims": {"type": "array", "items": {"type": "string"},
                            "description": "Dimensions to reduce over."},
            "op": {"type": "string",
                   "description": "Reduction op, e.g. 'avg', 'sum', 'min', 'max'."},
            "ssh_config": _SSH_CONFIG,
            "mesh_path": _MESH_PATH,
        },
        ["path", "variable", "reduce_dims", "op"],
    ),
    "dump_cdl": _obj(
        {
            "path": _PATH,
            "variables": {"type": ["array", "null"],
                          "items": {"type": "string"}},
            "header_only": {"type": "boolean"},
            "ssh_config": _SSH_CONFIG,
        },
        ["path"],
    ),
    "find_region": _obj(
        {"name": {"type": "string",
                  "description": "Region name (case-insensitive)."}},
        ["name"],
    ),
    "slice_along_section": _obj(
        {
            "mesh_path": {"type": "string"},
            "lat1": {"type": "number"},
            "lon1": {"type": "number"},
            "lat2": {"type": "number"},
            "lon2": {"type": "number"},
            "n_samples": {"type": "integer",
                          "description": "Number of points to sample along the section."},
            "convention": _CONVENTION,
        },
        ["mesh_path", "lat1", "lon1", "lat2", "lon2", "n_samples"],
    ),
}


def schema_for(name: str) -> dict[str, Any]:
    """Return the inputSchema for `name`, or a permissive object
    schema (still with a non-empty `properties`) for an unknown tool
    so registration never regresses to the empty `{"type": "object"}`."""
    return TOOL_SCHEMAS.get(
        name,
        {"type": "object", "properties": {}, "additionalProperties": True},
    )
