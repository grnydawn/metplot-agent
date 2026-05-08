# src/mcp/netcdf_reader/lifecycle.py
"""⤴ format-agnostic — eligible for _core/ lift.

Lifecycle hooks. cleanup_old_slice_dirs() runs at MCP server startup
and removes slice temp directories from previous sessions.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


def cleanup_old_slice_dirs(*, keep: str) -> None:
    base = Path.cwd() / ".metplot" / "slices"
    if not base.exists():
        return
    for child in base.iterdir():
        if child.is_dir() and child.name != keep:
            shutil.rmtree(child, ignore_errors=True)


_POOLS: list[Any] = []


def register_pool(pool: Any) -> None:
    _POOLS.append(pool)


def on_shutdown() -> None:
    for p in _POOLS:
        try:
            p.close_all()
        except Exception:
            pass
    _POOLS.clear()
