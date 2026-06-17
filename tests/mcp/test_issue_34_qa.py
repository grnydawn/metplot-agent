# tests/mcp/test_issue_34_qa.py
"""super-board QA suite for issue #34 — MCP tools do not accept arguments.

One observable test per acceptance criterion, written by the Tester lane
to independently verify the Builder's fix (PR #35). These tests are
complementary to the Builder's regression guards: they cross-check the
declared `inputSchema.required` against the *live* Python signatures of
the dispatched tool functions, drive the real MCP `list_tools` request
handler for both servers, and assert that the exact error strings quoted
in the original bug report no longer occur.

Root cause (confirmed): both servers registered every tool with the empty
`{"type": "object"}` inputSchema, so the agent runtime had no parameter
signature and `dispatch(name, args)` always raised
"missing required positional argument".
"""
from __future__ import annotations

import asyncio
import inspect as _ins

import pytest

from src.mcp.netcdf_reader import schemas as nc_schemas
from src.mcp.netcdf_reader import server as nc_server
from src.mcp.plot_renderer import schemas as plot_schemas
from src.mcp.plot_renderer import server as plot_server


@pytest.fixture
def sample_nc(tmp_path):
    """A real 3D CF NetCDF file (time, lat, lon) standing in for the
    `/tmp/sample.nc` from the original Copilot-CLI repro. Self-contained
    so this suite runs without the netcdf_reader conftest fixtures."""
    import numpy as np
    import xarray as xr

    times = np.array(["2024-09-01", "2024-09-02", "2024-09-03"],
                     dtype="datetime64[D]")
    lat = np.linspace(-90, 90, 19)
    lon = np.linspace(0, 357.5, 144)
    rng = np.random.default_rng(1)
    data = rng.normal(290, 5, size=(3, 19, 144)).astype("float32")
    ds = xr.Dataset(
        {"tos": xr.DataArray(
            data, dims=("time", "lat", "lon"),
            coords={"time": times, "lat": lat, "lon": lon},
            attrs={"long_name": "Sea Surface Temperature", "units": "K",
                   "standard_name": "sea_surface_temperature"})},
        attrs={"Conventions": "CF-1.7"},
    )
    ds["lat"].attrs.update({"units": "degrees_north"})
    ds["lon"].attrs.update({"units": "degrees_east"})
    p = tmp_path / "sample.nc"
    ds.to_netcdf(p)
    return p


# Map each dispatchable netcdf-reader tool to the callable dispatch invokes,
# so we can read its *real* keyword signature and compare to the schema.
def _nc_tool_funcs() -> dict[str, object]:
    from src.mcp.netcdf_reader.tools import (
        compute_stats as _stats,
        dump_cdl as _dump_cdl,
        find as _find,
        inspect as _inspect,
        peek as _peek,
        read_slice as _slice,
        reduce_variable as _reduce_var,
        resolve_spec as _spec,
    )
    from src.mcp.netcdf_reader.regions import find_region_tool
    from src.mcp.netcdf_reader.sections import slice_along_section_tool
    from src.mcp.netcdf_reader.selectors_unstructured import (
        cells_in_bbox_tool,
        find_nearest_cell_tool,
    )

    return {
        "inspect": _inspect.inspect,
        "resolve_spec": _spec.resolve_spec,
        "peek": _peek.peek,
        "read_slice": _slice.read_slice,
        "compute_stats": _stats.compute_stats,
        "find_variables": _find.find_variables,
        "find_time": _find.find_time,
        "find_nearest_cell": find_nearest_cell_tool,
        "cells_in_bbox": cells_in_bbox_tool,
        "reduce_variable": _reduce_var.reduce_variable,
        "dump_cdl": _dump_cdl.dump_cdl,
        "find_region": find_region_tool,
        "slice_along_section": slice_along_section_tool,
        # regrid_to_centers is dispatched as fn(args["spec"]); handled below.
    }


def _required_from_signature(func) -> set[str]:
    """No-default, non-injected keyword params of a tool function."""
    req: set[str] = set()
    for pname, p in _ins.signature(func).parameters.items():
        if pname == "adapter":  # injected by dispatch, never a caller arg
            continue
        if p.kind in (p.VAR_KEYWORD, p.VAR_POSITIONAL):
            continue
        if p.default is _ins.Parameter.empty:
            req.add(pname)
    return req


# --------------------------------------------------------------------------
# AC1 — Schemas expose parameters (required matches the real signatures)
# --------------------------------------------------------------------------
def test_ac1_netcdf_schema_required_matches_live_signatures():
    """Every netcdf-reader tool's `required` equals the no-default params of
    the function dispatch actually calls — and lists all 14 tools."""
    names = nc_server.list_tool_names()
    assert len(names) == 14, names

    funcs = _nc_tool_funcs()
    mismatches = {}
    for name in names:
        schema = nc_schemas.schema_for(name)
        declared = set(schema.get("required", []))
        props = schema.get("properties", {})
        assert props, f"{name}: inputSchema.properties is empty/missing"

        if name == "regrid_to_centers":
            expected = {"spec"}  # dispatch calls regrid_to_centers(args["spec"])
        else:
            expected = _required_from_signature(funcs[name])

        if declared != expected:
            mismatches[name] = {"declared": sorted(declared),
                                "from_signature": sorted(expected)}
        # every required param must be documented in properties
        for r in declared:
            assert r in props, f"{name}: required '{r}' missing from properties"
    assert not mismatches, mismatches


def test_ac1_plot_renderer_exposes_spec_with_fields():
    """All 4 render tools require a `spec` object whose nested `properties`
    document the renderer-specific fields (values/series/time/etc.)."""
    names = plot_server.list_tool_names()
    assert len(names) == 4, names
    for name in names:
        schema = plot_schemas.schema_for(name)
        assert schema.get("required") == ["spec"], name
        spec = schema["properties"]["spec"]
        assert spec.get("type") == "object", name
        assert spec.get("properties"), f"{name}: spec has no documented fields"


def test_ac1_live_list_tools_handler_returns_populated_schemas():
    """Drive the real MCP `list_tools` request handler for BOTH servers and
    assert zero tools fall back to the empty `{'type': 'object'}` shape."""
    import mcp.types as types

    for srv_mod, expected_count in (
        (nc_server, 14),
        (plot_server, 4),
    ):
        server = srv_mod.make_server()
        handler = server.request_handlers[types.ListToolsRequest]
        result = asyncio.run(handler(types.ListToolsRequest(method="tools/list")))
        tools = result.root.tools
        assert len(tools) == expected_count
        empty = [t.name for t in tools
                 if not t.inputSchema.get("properties")
                 or t.inputSchema == {"type": "object"}]
        assert not empty, f"{srv_mod.__name__}: empty-schema tools: {empty}"


# --------------------------------------------------------------------------
# AC2 — Live calls succeed with arguments passed through
# --------------------------------------------------------------------------
def test_ac2_inspect_with_path_returns_ok(sample_nc):
    out = nc_server.dispatch("inspect", {"path": str(sample_nc)})
    assert out["ok"] is True, out.get("error")
    assert "result" in out


def test_ac2_read_slice_with_path_and_variable_returns_data(sample_nc):
    out = nc_server.dispatch(
        "read_slice",
        {"path": str(sample_nc), "variable": "tos", "lat": 0.0, "lon": 0.0},
    )
    assert out["ok"] is True, out.get("error")
    assert out["result"], "read_slice returned an empty result payload"


# --------------------------------------------------------------------------
# AC3 — Missing-arg path is graceful (structured error, not a crash)
# --------------------------------------------------------------------------
def test_ac3_missing_required_arg_returns_error_envelope():
    """The exact failing calls from the bug report now return a structured
    error envelope rather than raising an unhandled exception."""
    out = nc_server.dispatch("inspect", {})  # 'path' omitted
    assert out["ok"] is False
    assert out["error"]["code"] == "internal_error"
    assert "bad arguments for inspect" in out["error"]["message"]

    out2 = nc_server.dispatch("read_slice", {})  # 'path' + 'variable' omitted
    assert out2["ok"] is False
    assert "bad arguments for read_slice" in out2["error"]["message"]


def test_ac3_missing_spec_returns_error_envelope(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = plot_server.dispatch("render_timeseries", {"spec": {}})
    assert out["ok"] is False
    assert out["error"]["code"] in ("invalid_spec", "internal_render_error")


# --------------------------------------------------------------------------
# AC4 — Regression guard: no empty `{"type": "object"}` schema anywhere
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "schemas_mod, server_mod",
    [(nc_schemas, nc_server), (plot_schemas, plot_server)],
)
def test_ac4_no_tool_uses_the_empty_object_schema(schemas_mod, server_mod):
    for name in server_mod.list_tool_names():
        schema = schemas_mod.schema_for(name)
        assert schema != {"type": "object"}, name
        assert schema.get("type") == "object", name
        assert schema.get("properties"), f"{name}: empty/missing properties"


# --------------------------------------------------------------------------
# AC5 — Copilot-CLI smoke: inspect + timeseries fully through MCP dispatch
# --------------------------------------------------------------------------
def test_ac5_inspect_then_timeseries_flow_through_mcp(sample_nc, tmp_path, monkeypatch):
    """Reproduce the originally-failing Copilot-CLI flow end-to-end using
    only MCP dispatch — no raw netCDF4 / matplotlib fallback. The original
    report quoted three failures; assert none of them recur."""
    monkeypatch.chdir(tmp_path)

    insp = nc_server.dispatch("inspect", {"path": str(sample_nc)})
    assert insp["ok"] is True, insp.get("error")

    sl = nc_server.dispatch(
        "read_slice",
        {"path": str(sample_nc), "variable": "tos", "lat": 0.0, "lon": 0.0},
    )
    assert sl["ok"] is True, sl.get("error")

    # Build a small 1D series from the slice (or a synthetic fallback) and
    # render it through the plot-renderer MCP tool.
    res = sl["result"]
    values = res.get("values") or res.get("data") or [290.0, 291.0, 292.0]
    flat = list(values)
    while flat and isinstance(flat[0], list):
        flat = flat[0]
    flat = flat[:3] or [290.0, 291.0, 292.0]
    time_axis = ["2024-09-01", "2024-09-02", "2024-09-03"][: len(flat)]

    plot = plot_server.dispatch(
        "render_timeseries",
        {"spec": {"values": flat, "time": time_axis,
                  "label": "tos @ (0,0)", "title": "issue-34 QA smoke"}},
    )
    assert plot["ok"] is True, plot.get("error")
    assert plot["result"]["output_path"].endswith(".png")

    # None of the three originally-quoted failure strings may appear.
    blob = repr([insp, sl, plot])
    assert "missing 1 required positional argument" not in blob
    assert "missing 2 required positional arguments" not in blob
    assert "provide `series` or `values+time`" not in blob
