"""MCP server: NetCDF inspection and slicing.

Exposes tools for AI agents to read NetCDF files without loading the full
arrays into the model's context. The server returns structured metadata and
numerical slices on demand.

Status: scaffold. Tool signatures defined; bodies are TODO.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

# Imports gated so the file is importable without the full MCP/xarray stack
# during build/lint.
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
except ImportError:  # pragma: no cover
    Server = None  # type: ignore[assignment]
    stdio_server = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


# ----- public tool implementations ------------------------------------------


def inspect(path: str) -> dict[str, Any]:
    """Return a structured summary of a NetCDF file.

    See README.md for the full output schema.
    """
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return {"error": f"file not found: {p}"}

    cache = _cache_path(p)
    if cache.exists():
        try:
            return json.loads(cache.read_text())
        except json.JSONDecodeError:
            pass

    # TODO: implement using xarray.open_dataset(p, decode_times=True)
    #   - variable list with dims, shape, units, long_name
    #   - coordinate ranges
    #   - longitude convention detection
    #   - calendar detection
    #   - staggered-grid detection
    #   - warnings for non-monotonic coords, missing units, etc.
    summary: dict[str, Any] = {
        "path": str(p),
        "variables": [],
        "coords": [],
        "dims": {},
        "time": None,
        "spatial": None,
        "vertical": None,
        "attrs": {},
        "warnings": [],
        "_stub": True,
    }

    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(summary, indent=2))
    return summary


def read_slice(
    path: str,
    variable: str,
    *,
    time: Any = None,
    level: Any = None,
    lat: Any = None,
    lon: Any = None,
    region: str | None = None,
    regrid: str | None = None,
) -> dict[str, Any]:
    """Read a slice of a variable. See README.md for the schema."""
    # TODO: implement with xarray .sel/.isel + the regions.json lookup
    return {"error": "not implemented", "_stub": True}


def compute_stats(
    path: str,
    variable: str,
    *,
    time: Any = None,
    level: Any = None,
    lat: Any = None,
    lon: Any = None,
    region: str | None = None,
) -> dict[str, Any]:
    """Cheap summary stats for a (sub)slice."""
    # TODO: implement with xarray; avoid loading full array, use .min().load() etc.
    return {"error": "not implemented", "_stub": True}


def regrid_to_centers(
    path: str,
    variable: str,
    *,
    time: Any = None,
    level: Any = None,
    lat: Any = None,
    lon: Any = None,
    region: str | None = None,
) -> dict[str, Any]:
    """Interpolate a staggered-grid variable to cell centers."""
    # TODO: detect U vs V vs scalar grid from coordinate variables; interpolate.
    return {"error": "not implemented", "_stub": True}


# ----- helpers --------------------------------------------------------------


def _cache_path(path: Path) -> Path:
    h = hashlib.sha1(str(path).encode()).hexdigest()[:16]
    return Path.cwd() / ".ncplot" / "inspections" / f"{h}.json"


# ----- MCP server wiring ----------------------------------------------------


def make_server() -> "Server":
    if Server is None:
        raise RuntimeError("mcp package not installed; install with [mcp] extra")

    server = Server("netcdf-reader")

    @server.list_tools()  # type: ignore[misc]
    async def _list_tools():
        # TODO: return mcp.types.Tool objects describing the four tools above.
        return []

    @server.call_tool()  # type: ignore[misc]
    async def _call_tool(name: str, arguments: dict[str, Any]):
        if name == "inspect":
            return inspect(**arguments)
        if name == "read_slice":
            return read_slice(**arguments)
        if name == "compute_stats":
            return compute_stats(**arguments)
        if name == "regrid_to_centers":
            return regrid_to_centers(**arguments)
        return {"error": f"unknown tool: {name}"}

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
