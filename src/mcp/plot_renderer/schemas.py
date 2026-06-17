# src/mcp/plot_renderer/schemas.py
"""JSON Schema (`inputSchema`) definitions for every plot-renderer tool.

Fixes the bug where the 4 render tools were registered with the empty
`{"type": "object"}` shape (no `properties`), so the agent runtime had
no signature to pass a `spec` through. `server.dispatch` unwraps
`args.get("spec", args)`, so the public contract is a single `spec`
object argument carrying the plot definition.

The `spec` shape is intentionally flexible: each renderer accepts
either a structured `series` list or the `values + axis` sugar (see
`adapter.normalize_*`), so per-field `required` lives in the runtime
validator (`InvalidSpecError`), not the JSON Schema. The schema's job
here is to expose `spec` as a non-empty, documented object so the
calling agent can pass arguments at all.
"""
from __future__ import annotations

from typing import Any

# Presentation fields shared by every renderer's spec.
_COMMON_SPEC_PROPS: dict[str, Any] = {
    "title": {"type": "string"},
    "xlabel": {"type": "string"},
    "ylabel": {"type": "string"},
    "colormap": {"type": "string"},
    "style_template": {"type": "string"},
    "format": {"type": "string", "description": "Output format, e.g. 'png'."},
    "dpi": {"type": "integer"},
    "output_path": {"type": "string",
                    "description": "Where to write the figure. Auto-named if omitted."},
}


def _spec_schema(extra_props: dict[str, Any], description: str) -> dict[str, Any]:
    props = {**_COMMON_SPEC_PROPS, **extra_props}
    return {
        "type": "object",
        "properties": {
            "spec": {
                "type": "object",
                "description": description,
                "properties": props,
                # Renderers accept extra keys (per-series color, etc.).
                "additionalProperties": True,
            }
        },
        "required": ["spec"],
        "additionalProperties": False,
    }


_SERIES_PROP = {
    "type": "array",
    "description": "Explicit series list; alternative to values+axis sugar.",
    "items": {"type": "object"},
}
_VALUES_PROP = {
    "type": "array",
    "description": "Data values (sugar form). Pair with the axis array.",
}


TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "render_map": _spec_schema(
        {
            "values": {"type": "array",
                       "description": "2D value grid (n_lat × n_lon)."},
            "lat": {"type": "array", "description": "Latitude coordinates."},
            "lon": {"type": "array", "description": "Longitude coordinates."},
        },
        "Map plot spec: 2D values plus lat/lon coordinates.",
    ),
    "render_timeseries": _spec_schema(
        {
            "series": _SERIES_PROP,
            "values": _VALUES_PROP,
            "time": {"type": "array",
                     "description": "Time axis (ISO strings) — pair with values."},
            "label": {"type": "string"},
            "trendline": {"type": "string",
                          "description": "Optional trendline: 'linear' or 'lowess'."},
        },
        "Timeseries spec: provide `series`, or `values` + `time` sugar.",
    ),
    "render_profile": _spec_schema(
        {
            "series": _SERIES_PROP,
            "values": _VALUES_PROP,
            "vertical": {"type": "array",
                         "description": "Vertical axis — pair with values."},
            "label": {"type": "string"},
        },
        "Vertical-profile spec: provide `series`, or `values` + `vertical` sugar.",
    ),
    "render_section": _spec_schema(
        {
            "values": {"type": "array",
                       "description": "2D section values."},
            "distance": {"type": "array",
                         "description": "Along-section distance axis."},
            "vertical": {"type": "array", "description": "Vertical axis."},
        },
        "Cross-section spec: 2D values over distance × vertical.",
    ),
}


def schema_for(name: str) -> dict[str, Any]:
    """Return the inputSchema for `name`, or a permissive spec-bearing
    object schema for an unknown tool so registration never regresses
    to the empty `{"type": "object"}` shape."""
    return TOOL_SCHEMAS.get(
        name,
        {
            "type": "object",
            "properties": {
                "spec": {"type": "object",
                         "description": "Plot definition.",
                         "additionalProperties": True}
            },
            "required": ["spec"],
            "additionalProperties": False,
        },
    )
