# tests/mcp/netcdf_reader/unit/test_tool_schemas.py
"""Regression guard for issue #34 — netcdf-reader tools must expose
their parameters in `inputSchema` (not the empty `{"type": "object"}`
shape that prevented the agent runtime from passing arguments)."""
import asyncio

from src.mcp.netcdf_reader import schemas
from src.mcp.netcdf_reader.server import dispatch, list_tool_names

# Minimum required params each tool must surface in `inputSchema.required`.
EXPECTED_REQUIRED = {
    "inspect": {"path"},
    "resolve_spec": {"path", "variable"},
    "regrid_to_centers": {"spec"},
    "peek": {"path", "variable"},
    "read_slice": {"path", "variable"},
    "compute_stats": {"path", "variable"},
    "find_variables": {"path", "hint"},
    "find_time": {"path", "hint"},
    "find_nearest_cell": {"mesh_path", "lat", "lon"},
    "cells_in_bbox": {"mesh_path", "lat_min", "lat_max", "lon_min", "lon_max"},
    "reduce_variable": {"path", "variable", "reduce_dims", "op"},
    "dump_cdl": {"path"},
    "find_region": {"name"},
    "slice_along_section": {"mesh_path", "lat1", "lon1", "lat2", "lon2", "n_samples"},
}


def test_every_tool_has_a_schema():
    """All 14 dispatchable tools have an explicit schema entry."""
    assert set(list_tool_names()) == set(schemas.TOOL_SCHEMAS)
    assert len(list_tool_names()) == 14


def test_no_schema_is_the_empty_object_shape():
    """AC4 — no tool's inputSchema is the bare `{"type": "object"}`
    (or any object schema with an empty/absent `properties` map)."""
    for name in list_tool_names():
        schema = schemas.schema_for(name)
        assert schema.get("type") == "object"
        props = schema.get("properties")
        assert props, f"{name} has empty/missing properties: {schema!r}"
        assert schema != {"type": "object"}


def test_required_params_are_exposed():
    """AC1 — each tool's `required` names exactly its no-default params,
    and every required param is present in `properties`."""
    for name, expected in EXPECTED_REQUIRED.items():
        schema = schemas.schema_for(name)
        required = set(schema.get("required", []))
        assert required == expected, f"{name}: {required} != {expected}"
        for param in required:
            assert param in schema["properties"], f"{name} missing prop {param}"


def test_list_tools_via_server_uses_schemas():
    """The real MCP `list_tools` request handler returns the populated
    schemas (not the empty shape) for every tool — guards the wiring
    between the server and `schemas.schema_for`."""
    import mcp.types as types

    from src.mcp.netcdf_reader import server as srv

    s = srv.make_server()
    handler = s.request_handlers[types.ListToolsRequest]
    result = asyncio.run(handler(types.ListToolsRequest(method="tools/list")))
    tools = result.root.tools
    by_name = {t.name: t for t in tools}
    assert set(by_name) == set(list_tool_names())
    for name, tool in by_name.items():
        assert tool.inputSchema != {"type": "object"}
        assert tool.inputSchema.get("properties"), name


def test_missing_required_arg_is_graceful(cf_3d_file):
    """AC3 — calling a tool without a required arg returns a structured
    error envelope (the TypeError guard), not an unhandled exception."""
    out = dispatch("inspect", {})  # 'path' omitted
    assert out["ok"] is False
    assert "bad arguments for inspect" in out["error"]["message"]
