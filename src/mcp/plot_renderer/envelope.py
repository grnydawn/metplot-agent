"""⤴ format-agnostic — eligible for _core/ lift.

Locked cross-MCP envelope shape. Copied from cycle-1's envelope.py.
Keep these schemas in sync if either side changes.
"""
from __future__ import annotations

from typing import Any


class ErrorCode:
    INVALID_SPEC                  = "invalid_spec"
    OUTPUT_PATH_INVALID           = "output_path_invalid"
    OUTPUT_DIR_UNWRITABLE         = "output_dir_unwritable"
    SLICE_FILE_UNREADABLE         = "slice_file_unreadable"
    INTERNAL_RENDER_ERROR         = "internal_render_error"
    UNSUPPORTED_FORMAT            = "unsupported_format"
    FORMAT_EXTENSION_MISMATCH     = "format_extension_mismatch"
    INVALID_DPI                   = "invalid_dpi"
    TRENDLINE_DEPENDENCY_MISSING  = "trendline_dependency_missing"
    UNKNOWN_TOOL                  = "unknown_tool"


class AmbiguitySubcode:
    CARTOPY_MISSING       = "cartopy_missing"
    UNKNOWN_COLORMAP      = "unknown_colormap"
    UNKNOWN_PROJECTION    = "unknown_projection"
    EMPTY_SLICE           = "empty_slice"
    ALL_NAN               = "all_nan"


class WarningCode:
    AUTO_DOWNSAMPLED              = "auto_downsampled"
    CONSTANT_FIELD                = "constant_field"
    HIGH_NAN_FRACTION             = "high_nan_fraction"
    LON_SHIFT_APPLIED             = "lon_shift_applied"
    STYLE_TEMPLATE_PARTIAL        = "style_template_partially_applied"
    VCENTER_OUTSIDE_DATA_RANGE    = "vcenter_outside_data_range"
    COLOR_CYCLE_EXCEEDED          = "color_cycle_exceeded"
    PERCENTILE_CLIP_APPLIED       = "percentile_clip_applied"


def success(result: dict[str, Any], *,
            warnings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"ok": True, "result": result, "warnings": warnings or []}


def error(code: str, message: str, *,
          context: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": False,
            "error": {"code": code, "message": message,
                      "context": context or {}}}


def ambiguous(*, subcode: str, message: str,
              candidates: list[dict[str, Any]],
              retry_with_param: str | None = None,
              context: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": False,
            "error": {"code": "ambiguous",
                      "subcode": subcode,
                      "message": message,
                      "candidates": candidates,
                      "retry_with_param": retry_with_param,
                      "context": context or {}}}


def warn(code: str, message: str,
         context: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"code": code, "message": message, "context": context or {}}
