"""⤴ format-agnostic — eligible for _core/ lift.

Render-oracle JSON capture. Spec §6.

Per-tool drawn fields are added in Task 24. This module exposes
common helpers; tools call `capture_common` then enrich with their
own `drawn` fields and call `finalize`.
"""
from __future__ import annotations

from typing import Any


ORACLE_SCHEMA_VERSION = 1

REQUIRED_TOP_LEVEL_FIELDS = {
    "oracle_schema_version", "tool", "output", "data",
    "style_resolution", "drawn", "style_template_applied",
}

# Minimum presentation fields present in every resolved spec
_REQUIRED_PRESENTATION_FIELDS = {
    "colormap", "colorbar_position", "gridlines", "font_scale", "aspect",
}


class OracleIncomplete(RuntimeError):
    pass


def _output_block(fig: Any, output_path: str, size_bytes: int,
                  fmt: str | None, dpi: int | None) -> dict[str, Any]:
    width_px = int(fig.get_size_inches()[0] * (dpi or 100))
    height_px = int(fig.get_size_inches()[1] * (dpi or 100))
    if fmt is None:
        from pathlib import Path
        fmt = Path(output_path).suffix.lstrip(".") or "png"
    return {
        "path": output_path,
        "format": fmt,
        "size_bytes": size_bytes,
        "dpi": dpi or 0,
        "width_px": width_px,
        "height_px": height_px,
    }


def _style_resolution_block(
    sources: dict[str, str], resolved: dict[str, Any],
) -> dict[str, Any]:
    block: dict[str, Any] = {}
    for field in _REQUIRED_PRESENTATION_FIELDS:
        if field not in sources:
            raise OracleIncomplete(
                f"style_resolution missing source for required field {field!r}")
        block[field] = {"value": resolved.get(field),
                         "source": sources[field]}
    # Optional fields if present:
    for field in ("projection",):
        if field in resolved or field in sources:
            block[field] = {"value": resolved.get(field),
                             "source": sources.get(field, "library_default")}
    return block


def capture_common(*,
    fig: Any, tool: str,
    resolved_spec: dict[str, Any],
    style_resolution_sources: dict[str, str],
    safety_actions: dict[str, Any],
    output_path: str, output_size_bytes: int,
    data_shape: list[int],
) -> dict[str, Any]:
    """Build the common (non-tool-specific) oracle skeleton.

    Tools enrich `drawn` with their own per-tool fields and set
    `style_template_applied` before sending the oracle out.
    """
    out_block = _output_block(
        fig, output_path, output_size_bytes,
        fmt=resolved_spec.get("format"),
        dpi=resolved_spec.get("dpi"),
    )
    return {
        "oracle_schema_version": ORACLE_SCHEMA_VERSION,
        "tool": tool,
        "output": out_block,
        "data": {
            "shape": list(data_shape),
            "plotted_min": safety_actions.get("plotted_min"),
            "plotted_max": safety_actions.get("plotted_max"),
            "nan_fraction": safety_actions.get("nan_fraction", 0.0),
            "applied_downsample": safety_actions.get("applied_downsample"),
            "applied_lon_shift": safety_actions.get("applied_lon_shift"),
            "applied_clip_pct": safety_actions.get("applied_clip_pct"),
            "vmin_used": safety_actions.get("vmin_used"),
            "vmax_used": safety_actions.get("vmax_used"),
        },
        "style_resolution": _style_resolution_block(
            style_resolution_sources, resolved_spec),
        "drawn": {},   # tool fills in
        "style_template_applied": None,   # tool fills in
    }


def finalize(oracle: dict[str, Any]) -> dict[str, Any]:
    """Validate the oracle has all required top-level fields. Raises
    OracleIncomplete if not."""
    missing = REQUIRED_TOP_LEVEL_FIELDS - set(oracle.keys())
    if missing:
        raise OracleIncomplete(
            f"oracle missing required top-level fields: {sorted(missing)}")
    return oracle
