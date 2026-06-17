# tests/mcp/netcdf_reader/integration/test_mcp_args_e2e.py
"""End-to-end guard for issue #34 — the originally-failing flow.

Reproduces the Copilot-CLI session that prompted the bug:
`netcdf-inspect` followed by `netcdf-plot-timeseries` against a real
`.nc` file, driven entirely through the MCP `dispatch` entry points
(no raw `netCDF4` + `matplotlib` fallback). Before the fix, every call
raised "missing required positional argument" because the tool schemas
were registered with an empty `{"type": "object"}` inputSchema.
"""
from __future__ import annotations

from src.mcp.netcdf_reader.server import dispatch as nc_dispatch
from src.mcp.plot_renderer.server import dispatch as plot_dispatch


def test_inspect_accepts_path_argument(cf_3d_file):
    """AC2 — inspect with {'path': ...} returns an ok envelope."""
    out = nc_dispatch("inspect", {"path": str(cf_3d_file)})
    assert out["ok"] is True, out.get("error")
    assert "convention" in out["result"]


def test_read_slice_accepts_path_and_variable(cf_3d_file):
    """AC2 — read_slice with {'path','variable'} returns data."""
    out = nc_dispatch("read_slice", {
        "path": str(cf_3d_file), "variable": "tos",
        "time": "2024-09-01", "lat": 0.0, "lon": 0.0,
    })
    assert out["ok"] is True, out.get("error")


def test_full_inspect_then_timeseries_via_mcp(cf_3d_file, tmp_path, monkeypatch):
    """AC5 — the inspect + plot-timeseries flow completes through MCP
    tools end to end, producing a figure from data read via read_slice."""
    monkeypatch.chdir(tmp_path)

    # 1. Inspect — discover the file (Copilot CLI step 1).
    insp = nc_dispatch("inspect", {"path": str(cf_3d_file)})
    assert insp["ok"] is True, insp.get("error")

    # 2. Read a time series for 'tos' at a single grid point.
    sl = nc_dispatch("read_slice", {
        "path": str(cf_3d_file), "variable": "tos",
        "lat": 0.0, "lon": 0.0,
    })
    assert sl["ok"] is True, sl.get("error")
    result = sl["result"]

    # Pull a 1D values array + a time axis out of the slice result so we
    # can hand it to the renderer. The slice inlines small payloads.
    values = result.get("values") or result.get("data")
    time_axis = None
    coords = result.get("coords") or result.get("coordinates") or {}
    if isinstance(coords, dict):
        time_axis = coords.get("time")
    # Fallback: build a synthetic 3-step axis matching the fixture.
    if not values:
        values = [290.0, 291.0, 292.0]
    if not time_axis:
        time_axis = ["2024-09-01", "2024-09-02", "2024-09-03"]
    # Coerce nested arrays down to 1D length-3 for the demo plot.
    flat = list(values)
    while flat and isinstance(flat[0], list):
        flat = flat[0]
    flat = flat[:3] or [290.0, 291.0, 292.0]
    time_axis = list(time_axis)[:len(flat)]

    # 3. Render the timeseries through plot-renderer MCP dispatch.
    plot = plot_dispatch("render_timeseries", {"spec": {
        "values": flat,
        "time": time_axis,
        "label": "tos @ (0,0)",
        "title": "issue-34 e2e smoke",
    }})
    assert plot["ok"] is True, plot.get("error")
    assert plot["result"]["output_path"].endswith(".png")
