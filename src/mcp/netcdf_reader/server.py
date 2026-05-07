"""MCP server entry point. Thin dispatch over the 8 callable tools.

Registers a Stop-style cleanup at startup that removes slice temp dirs
from previous sessions per the lifecycle hook in the spec.
"""
from __future__ import annotations

import asyncio
from typing import Any

from src.mcp.netcdf_reader import envelope, lifecycle
from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools import (
    compute_stats as _stats,
    find as _find,
    inspect as _inspect,
    peek as _peek,
    read_slice as _slice,
    resolve_spec as _spec,
    transforms as _transforms,
)

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    import mcp.types as types
except ImportError:
    Server = None
    stdio_server = None
    types = None

_ADAPTER = NetCDFAdapter()


def list_tool_names() -> list[str]:
    return ["inspect", "resolve_spec", "regrid_to_centers",
            "peek", "read_slice", "compute_stats",
            "find_variables", "find_time"]


def dispatch(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Internal dispatcher used by the MCP wrapper and by tests."""
    try:
        if name == "inspect":
            return _inspect.inspect(adapter=_ADAPTER, **args)
        if name == "resolve_spec":
            return _spec.resolve_spec(adapter=_ADAPTER, **args)
        if name == "regrid_to_centers":
            return _transforms.regrid_to_centers(args["spec"])
        if name == "peek":
            return _peek.peek(adapter=_ADAPTER, **args)
        if name == "read_slice":
            return _slice.read_slice(adapter=_ADAPTER, **args)
        if name == "compute_stats":
            return _stats.compute_stats(adapter=_ADAPTER, **args)
        if name == "find_variables":
            return _find.find_variables(adapter=_ADAPTER, **args)
        if name == "find_time":
            return _find.find_time(adapter=_ADAPTER, **args)
        return envelope.error("unknown_tool", f"unknown tool: {name}",
                              context={"name": name})
    except TypeError as e:
        return envelope.error("internal_error",
                              f"bad arguments for {name}: {e}",
                              context={"args": list(args.keys())})


def _session_id_from_lifecycle() -> str:
    from src.mcp.netcdf_reader.tools.read_slice import _session_id
    return _session_id()


def make_server() -> "Server":
    if Server is None:
        raise RuntimeError("mcp package not installed; install [mcp] extra")

    # Cleanup previous sessions' slice temp dirs at startup
    lifecycle.cleanup_old_slice_dirs(keep=_session_id_from_lifecycle())

    server = Server("netcdf-reader")

    @server.list_tools()  # type: ignore[misc]
    async def _list_tools() -> list[Any]:
        return [
            types.Tool(name=n, description=f"netcdf-reader.{n}",
                       inputSchema={"type": "object"})
            for n in list_tool_names()
        ]

    @server.call_tool()  # type: ignore[misc]
    async def _call_tool(name: str, arguments: dict[str, Any]) -> Any:
        result = dispatch(name, arguments or {})
        # MCP expects text content
        import json
        return [types.TextContent(type="text", text=json.dumps(result))]

    return server


def main() -> None:
    if stdio_server is None:
        raise RuntimeError("mcp package not installed; install [mcp] extra")
    server = make_server()

    async def _run() -> None:
        async with stdio_server() as (read, write):
            try:
                await server.run(read, write, server.create_initialization_options())
            finally:
                lifecycle.on_shutdown()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
