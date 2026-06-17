# tests/mcp/plot_renderer/unit/test_tool_schemas.py
"""Regression guard for issue #34 — plot-renderer tools must expose a
`spec` parameter in `inputSchema` (not the empty `{"type": "object"}`
shape that prevented the agent runtime from passing arguments)."""
import asyncio

from src.mcp.plot_renderer import schemas
from src.mcp.plot_renderer.server import dispatch, list_tool_names


def test_every_tool_has_a_schema():
    assert set(list_tool_names()) == set(schemas.TOOL_SCHEMAS)
    assert len(list_tool_names()) == 4


def test_no_schema_is_the_empty_object_shape():
    """AC4 — no tool's inputSchema is the bare `{"type": "object"}`
    (or any object schema with an empty/absent `properties` map)."""
    for name in list_tool_names():
        schema = schemas.schema_for(name)
        assert schema.get("type") == "object"
        props = schema.get("properties")
        assert props, f"{name} has empty/missing properties: {schema!r}"
        assert schema != {"type": "object"}


def test_spec_param_is_exposed():
    """AC1 — every renderer exposes `spec` as a required object property
    with its own non-empty nested `properties` map."""
    for name in list_tool_names():
        schema = schemas.schema_for(name)
        assert "spec" in schema["properties"], name
        assert schema.get("required") == ["spec"], name
        spec = schema["properties"]["spec"]
        assert spec.get("type") == "object", name
        assert spec.get("properties"), f"{name} spec has no documented fields"


def test_list_tools_via_server_uses_schemas():
    """The real MCP `list_tools` request handler returns the populated
    schemas (not the empty shape) for every tool."""
    import mcp.types as types

    from src.mcp.plot_renderer import server as srv

    s = srv.make_server()
    handler = s.request_handlers[types.ListToolsRequest]
    result = asyncio.run(handler(types.ListToolsRequest(method="tools/list")))
    tools = result.root.tools
    by_name = {t.name: t for t in tools}
    assert set(by_name) == set(list_tool_names())
    for name, tool in by_name.items():
        assert tool.inputSchema != {"type": "object"}
        assert tool.inputSchema.get("properties"), name


def test_missing_spec_is_graceful(tmp_path, monkeypatch):
    """AC3 — calling a renderer without usable spec data returns a
    structured error envelope, not an unhandled exception."""
    monkeypatch.chdir(tmp_path)
    out = dispatch("render_timeseries", {"spec": {}})
    assert out["ok"] is False
    assert out["error"]["code"] in ("invalid_spec", "internal_render_error")
