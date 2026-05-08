"""⤴ format-agnostic — eligible for _core/ lift.

Deterministic application of a `style_template` dict onto a working
spec. See spec §8.

Precedence rule: explicit_spec[field] > template[field] > library_default.
The library default lookup happens at the call site (`render_*`),
not here — this module only resolves explicit vs template.
"""
from __future__ import annotations

from typing import Any, Callable

# A mapping entry returns: (spec_field, mapped_value, ok, reason).
# - spec_field: which field of the working spec receives the value.
# - mapped_value: the value to write (may be a dict for fan-out).
# - ok: True if the template value is recognized and applicable.
# - reason: when ok=False, why it was ignored.
MapResult = tuple[str | dict[str, Any], Any, bool, str]
Mapper = Callable[[Any], MapResult]


def _map_colormap_name(value: Any) -> MapResult:
    if not isinstance(value, str):
        return ("colormap", None, False, "colormap_name_not_string")
    return ("colormap", value, True, "")


def _map_colormap_kind(value: Any) -> MapResult:
    table = {
        "sequential":  ("colormap", "viridis"),
        "diverging":   ({"colormap": "RdBu_r", "vcenter": 0.0}, None),
        "categorical": ("colormap", "tab10"),
    }
    if value not in table:
        return ("colormap", None, False, "unknown_colormap_kind")
    field, val = table[value]
    if isinstance(field, dict):
        # Multi-field fan-out
        return (field, None, True, "")
    return (field, val, True, "")


def _map_vcenter(value: Any) -> MapResult:
    if not isinstance(value, (int, float)):
        return ("vcenter", None, False, "vcenter_not_number")
    return ("vcenter", float(value), True, "")


def _map_clip_pct(value: Any) -> MapResult:
    if not (isinstance(value, (list, tuple)) and len(value) == 2
            and all(isinstance(v, (int, float)) for v in value)):
        return ("clip_pct", None, False, "clip_pct_must_be_two_numbers")
    return ("clip_pct", [float(value[0]), float(value[1])], True, "")


def _map_projection_family(value: Any) -> MapResult:
    table = {
        "plate_carree":        "PlateCarree",
        "robinson":            "Robinson",
        "polar_stereo_north":  "NorthPolarStereo",
        "polar_stereo_south":  "SouthPolarStereo",
        "lambert_conformal":   "LambertConformal",
        "mercator":            "Mercator",
    }
    if value not in table:
        return ("projection", None, False, "unknown_projection_family")
    return ("projection", table[value], True, "")


def _map_colorbar_position(value: Any) -> MapResult:
    if value not in {"right", "left", "top", "bottom", "none"}:
        return ("colorbar_position", None, False, "unknown_colorbar_position")
    return ("colorbar_position", value, True, "")


def _map_legend_placement(value: Any) -> MapResult:
    if value not in {"best", "outside_right", "outside_bottom", "none"}:
        return ("legend_placement", None, False, "unknown_legend_placement")
    return ("legend_placement", value, True, "")


def _map_gridlines(value: Any) -> MapResult:
    if value not in {"none", "light", "heavy"}:
        return ("gridlines", None, False, "unknown_gridlines")
    return ("gridlines", value, True, "")


def _map_aspect(value: Any) -> MapResult:
    if value == "auto":
        return ("aspect", "auto", True, "")
    if isinstance(value, (int, float)):
        return ("aspect", float(value), True, "")
    return ("aspect", None, False, "aspect_not_number_or_auto")


def _map_font_scale(value: Any) -> MapResult:
    if not isinstance(value, (int, float)):
        return ("font_scale", None, False, "font_scale_not_number")
    clamped = max(0.7, min(1.5, float(value)))
    return ("font_scale", clamped, True, "")


def _map_advisory(field_name: str) -> Mapper:
    """Generator for advisory fields that flow through with a `_advisory_` prefix."""
    def _inner(value: Any) -> MapResult:
        return (f"_advisory_{field_name}", value, True, "")
    return _inner


_MAPPING: dict[str, Mapper] = {
    "colormap_name": _map_colormap_name,
    "colormap_kind": _map_colormap_kind,
    "vcenter":       _map_vcenter,
    "clip_pct":      _map_clip_pct,
}

_MAPPING.update({
    "projection_family":  _map_projection_family,
    "colorbar_position":  _map_colorbar_position,
    "legend_placement":   _map_legend_placement,
    "gridlines":          _map_gridlines,
    "aspect":             _map_aspect,
    "font_scale":         _map_font_scale,
    "extent_hint":        _map_advisory("extent_hint"),
    "title_placement":    _map_advisory("title_placement"),
    "label_density":      _map_advisory("label_density"),
})


def apply(
    spec: dict[str, Any], template: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply `template` to `spec` per the precedence rule.

    Returns (resolved, trace) where trace contains:
      - fields_applied: list[str] of template keys that wrote values
      - fields_ignored: list[{field, reason}]
    """
    resolved: dict[str, Any] = dict(spec)
    trace: dict[str, Any] = {"fields_applied": [], "fields_ignored": []}

    if template is None:
        return resolved, trace

    # colormap_name takes precedence over colormap_kind within a template:
    # if both present, drop colormap_kind first.
    seen_name = template.get("colormap_name") is not None
    for tmpl_field, value in template.items():
        if value is None:
            continue
        if tmpl_field == "colormap_kind" and seen_name:
            trace["fields_ignored"].append(
                {"field": tmpl_field,
                 "reason": "colormap_name_takes_precedence"})
            continue
        mapper = _MAPPING.get(tmpl_field)
        if mapper is None:
            trace["fields_ignored"].append(
                {"field": tmpl_field, "reason": "unknown_template_field"})
            continue
        spec_field, mapped_value, ok, reason = mapper(value)
        if not ok:
            trace["fields_ignored"].append(
                {"field": tmpl_field, "reason": reason})
            continue
        # Multi-field fan-out (dict spec_field carries {field: value} pairs)
        if isinstance(spec_field, dict):
            # Check if the primary output field (colormap) is already set;
            # if so, treat the whole template field as overridden.
            fan_fields = list(spec_field.keys())
            primary = fan_fields[0] if fan_fields else None
            if primary is not None and primary in resolved and resolved[primary] is not None:
                trace["fields_ignored"].append(
                    {"field": tmpl_field,
                     "reason": "overridden_by_explicit_spec"})
                continue
            applied_any = False
            for sf, mv in spec_field.items():
                if sf in resolved and resolved[sf] is not None:
                    continue
                resolved[sf] = mv
                applied_any = True
            if applied_any:
                trace["fields_applied"].append(tmpl_field)
            else:
                trace["fields_ignored"].append(
                    {"field": tmpl_field,
                     "reason": "overridden_by_explicit_spec"})
            continue
        # Single-field write
        if spec_field in resolved and resolved[spec_field] is not None:
            trace["fields_ignored"].append(
                {"field": tmpl_field,
                 "reason": "overridden_by_explicit_spec"})
            continue
        resolved[spec_field] = mapped_value
        trace["fields_applied"].append(tmpl_field)

    return resolved, trace
