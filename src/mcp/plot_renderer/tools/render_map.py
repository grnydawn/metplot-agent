"""FORMAT-SPECIFIC (cartopy-aware): map rendering.

This is the only file in cycle-2 that imports cartopy. The seam test
allows it; other tools must not import cartopy.
"""
from __future__ import annotations

from typing import Any

from src.mcp.plot_renderer import envelope

try:
    import cartopy.crs as ccrs  # type: ignore[import-not-found]
    import cartopy.feature as cfeature  # type: ignore[import-not-found]
    _CARTOPY_OK = True
    _CARTOPY_IMPORT_ERROR: str | None = None
except ImportError as e:
    ccrs = None  # type: ignore[assignment]
    cfeature = None  # type: ignore[assignment]
    _CARTOPY_OK = False
    _CARTOPY_IMPORT_ERROR = str(e)


def _cartopy_ambiguity() -> dict[str, Any]:
    return envelope.ambiguous(
        subcode="cartopy_missing",
        message=("cartopy is not installed. Install with "
                 "`uv pip install cartopy` (PROJ + GEOS C libs required) or "
                 "wait for cycle-5 auto-install."),
        candidates=[
            {"param": "install", "value": "uv pip install cartopy",
             "kind": "shell_command"},
            {"param": "install", "value": "conda install -c conda-forge cartopy",
             "kind": "shell_command"},
        ],
        retry_with_param=None,
        context={"import_error": _CARTOPY_IMPORT_ERROR},
    )


def render_map(spec: dict[str, Any]) -> dict[str, Any]:
    """Render a 2D lat/lon map. See spec §2.1."""
    if not _CARTOPY_OK:
        return _cartopy_ambiguity()
    # Drawing implementation lands in Task 30
    return envelope.error("internal_render_error",
                          "render_map drawing not implemented yet")
