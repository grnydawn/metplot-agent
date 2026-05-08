# src/mcp/plot_renderer/server.py
"""MCP server entry point. Thin dispatch over the 3 callable tools."""
from __future__ import annotations

import asyncio
from typing import Any

from src.mcp.plot_renderer import envelope
from src.mcp.plot_renderer.tools import (
    render_map as _map,
    render_profile as _profile,
    render_timeseries as _ts,
)

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    import mcp.types as types
except ImportError:  # pragma: no cover
    Server = None  # type: ignore[misc,assignment]
    stdio_server = None  # type: ignore[misc,assignment]
    types = None  # type: ignore[misc,assignment]


def list_tool_names() -> list[str]:
    return ["render_map", "render_timeseries", "render_profile"]


def dispatch(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Internal dispatcher used by the MCP wrapper and by tests."""
    spec = args.get("spec", args) if isinstance(args, dict) else {}
    try:
        if name == "render_map":
            return _map.render_map(spec)
        if name == "render_timeseries":
            return _ts.render_timeseries(spec)
        if name == "render_profile":
            return _profile.render_profile(spec)
        return envelope.error(
            "unknown_tool",
            f"unknown tool: {name}",
            context={"name": name, "available": list_tool_names()})
    except TypeError as e:
        return envelope.error(
            "internal_render_error",
            f"bad arguments for {name}: {e}",
            context={"args": list(args.keys()) if isinstance(args, dict) else []})


def make_server() -> "Server":
    if Server is None:
        raise RuntimeError("mcp package not installed; install with [mcp] extra")
    server = Server("plot-renderer")

    @server.list_tools()  # type: ignore[misc]
    async def _list_tools() -> list[Any]:
        return [
            types.Tool(name=n, description=f"plot-renderer.{n}",
                       inputSchema={"type": "object"})
            for n in list_tool_names()
        ]

    @server.call_tool()  # type: ignore[misc]
    async def _call_tool(name: str, arguments: dict[str, Any]) -> Any:
        result = dispatch(name, arguments or {})
        import json
        return [types.TextContent(type="text", text=json.dumps(result, default=str))]

    return server


def main() -> None:
    if stdio_server is None:
        raise RuntimeError("mcp package not installed; install with [mcp] extra")
    server = make_server()

    async def _run() -> None:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    asyncio.run(_run())


if __name__ == "__main__":
    main()
