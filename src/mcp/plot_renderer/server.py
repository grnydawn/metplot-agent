"""MCP server: matplotlib/cartopy plot rendering.

Pure rendering — no NetCDF awareness. Takes structured plot specs and
returns figure files plus reporting metadata.

Status: scaffold. Tool signatures defined; bodies are TODO.
"""

from __future__ import annotations

import logging
from typing import Any

Server: Any = None
stdio_server: Any = None

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
except ImportError:  # pragma: no cover
    pass

logger = logging.getLogger(__name__)


def render_map(spec: dict[str, Any]) -> dict[str, Any]:
    # TODO: matplotlib + cartopy
    #   - apply lon_convention shift if needed
    #   - apply percentile clip if clip_pct provided
    #   - choose default colormap if not given (router-style table)
    #   - draw coastlines, gridlines
    #   - save to spec["output_path"]
    return {"error": "not implemented", "_stub": True}


def render_timeseries(spec: dict[str, Any]) -> dict[str, Any]:
    # TODO
    return {"error": "not implemented", "_stub": True}


def render_profile(spec: dict[str, Any]) -> dict[str, Any]:
    # TODO
    return {"error": "not implemented", "_stub": True}


def render_cross_section(spec: dict[str, Any]) -> dict[str, Any]:
    # TODO
    return {"error": "not implemented", "_stub": True}


def render_hovmoller(spec: dict[str, Any]) -> dict[str, Any]:
    # TODO
    return {"error": "not implemented", "_stub": True}


# ----- MCP server wiring ----------------------------------------------------


_TOOLS = {
    "render_map": render_map,
    "render_timeseries": render_timeseries,
    "render_profile": render_profile,
    "render_cross_section": render_cross_section,
    "render_hovmoller": render_hovmoller,
}


def make_server() -> "Server":
    if Server is None:
        raise RuntimeError("mcp package not installed; install with [mcp] extra")

    server = Server("plot-renderer")

    @server.list_tools()  # type: ignore[misc]
    async def _list_tools():
        # TODO: return mcp.types.Tool objects for the five tools above.
        return []

    @server.call_tool()  # type: ignore[misc]
    async def _call_tool(name: str, arguments: dict[str, Any]):
        fn = _TOOLS.get(name)
        if fn is None:
            return {"error": f"unknown tool: {name}"}
        return fn(arguments.get("spec", arguments))

    return server


def main() -> None:
    import asyncio

    if stdio_server is None:
        raise RuntimeError("mcp package not installed; install with [mcp] extra")

    server = make_server()

    async def _run():
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    asyncio.run(_run())


if __name__ == "__main__":
    main()
