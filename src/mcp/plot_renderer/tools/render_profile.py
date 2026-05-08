"""⤴ format-agnostic — eligible for _core/ lift."""
from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from src.mcp.plot_renderer import (
    adapter, defaults as _defaults, envelope, lifecycle, oracle, style,
)

_PRESSURE_UNITS = {"Pa", "hPa"}


def _resolve_presentation(resolved: dict[str, Any], is_pressure: bool) -> dict[str, Any]:
    out = dict(resolved)
    # Apply pressure-specific defaults BEFORE library defaults so they win
    # over any log_scale=False in LIBRARY_DEFAULTS.
    if is_pressure:
        out.setdefault("log_scale", True)
        out.setdefault("invert_pressure", True)
    else:
        out.setdefault("log_scale", False)
        out.setdefault("invert_pressure", False)
    out.setdefault("colorbar_position", "none")
    out.setdefault("vertical_axis", "y")
    for k, v in _defaults.LIBRARY_DEFAULTS.items():
        out.setdefault(k, v)
    return out


def _sources(spec: dict[str, Any], trace: dict[str, Any]) -> dict[str, str]:
    explicit = set(spec.keys())
    applied = set(trace.get("fields_applied", []))
    sources: dict[str, str] = {}
    for field in ("colormap", "colorbar_position", "gridlines",
                   "font_scale", "aspect"):
        if field in explicit and spec[field] is not None:
            sources[field] = "explicit"
        elif field in applied:
            sources[field] = "style_template"
        else:
            sources[field] = "library_default"
    return sources


def render_profile(spec: dict[str, Any]) -> dict[str, Any]:
    """Render a vertical profile (single or multi). See spec §2.3."""
    try:
        try:
            series = adapter.normalize_1d_series(spec, axis_name="vertical")
        except adapter.InvalidSpecError as e:
            return envelope.error("invalid_spec", str(e))

        is_pressure = spec.get("vertical_units") in _PRESSURE_UNITS
        resolved, trace = style.apply(spec, spec.get("style_template"))
        resolved = _resolve_presentation(resolved, is_pressure)
        # User explicit overrides
        if "log_scale" in spec and spec["log_scale"] is not None:
            resolved["log_scale"] = spec["log_scale"]
        if "invert_pressure" in spec and spec["invert_pressure"] is not None:
            resolved["invert_pressure"] = spec["invert_pressure"]

        vertical_axis = spec.get("vertical_axis") or resolved["vertical_axis"]

        fig, ax = plt.subplots(figsize=(5.0, 6.0))
        color_cycle = plt.colormaps["tab10"].colors  # type: ignore[attr-defined]
        series_meta: list[dict[str, Any]] = []
        series_stats: list[dict[str, Any]] = []
        for i, s in enumerate(series):
            color = s.get("color") or color_cycle[i % len(color_cycle)]
            if vertical_axis == "y":
                ax.plot(s["values"], s["axis"], label=s["label"],
                        color=color, linestyle="-")
            else:
                ax.plot(s["axis"], s["values"], label=s["label"],
                        color=color, linestyle="-")
            series_meta.append({"label": s["label"],
                                  "n_points": int(s["values"].shape[0]),
                                  "color": str(color), "linestyle": "-"})
            finite = s["values"][np.isfinite(s["values"])]
            series_stats.append({"label": s["label"],
                                  "n_points": int(s["values"].shape[0]),
                                  "plotted_min": float(finite.min()) if finite.size else None,
                                  "plotted_max": float(finite.max()) if finite.size else None,
                                  "nan_fraction": (
                                      1.0 - float(finite.size) / float(s["values"].size)
                                      if s["values"].size else 0.0)})

        if resolved["log_scale"]:
            (ax.set_yscale if vertical_axis == "y" else ax.set_xscale)("log")
        if resolved["invert_pressure"]:
            (ax.invert_yaxis if vertical_axis == "y" else ax.invert_xaxis)()

        if spec.get("title"):
            ax.set_title(spec["title"])
        if spec.get("xlabel"):
            ax.set_xlabel(spec["xlabel"])
        if spec.get("ylabel"):
            ax.set_ylabel(spec["ylabel"])
        if len(series) > 1:
            ax.legend()
        ax.grid(resolved.get("gridlines") != "none", alpha=0.3)
        fig.tight_layout()

        fmt = resolved.get("format", "png")
        dpi = int(resolved.get("dpi", 150))
        lifecycle.validate_dpi(dpi)
        if spec.get("output_path"):
            try:
                output_path = lifecycle.resolve_output_path(
                    spec["output_path"], fmt=spec.get("format"))
            except lifecycle.FormatExtensionMismatch as e:
                plt.close(fig)
                return envelope.error("format_extension_mismatch", str(e))
            except lifecycle.UnsupportedFormat as e:
                plt.close(fig)
                return envelope.error("unsupported_format", str(e))
            except lifecycle.OutputPathInvalid as e:
                plt.close(fig)
                return envelope.error("output_path_invalid", str(e))
        else:
            output_path = lifecycle.auto_name(tool="profile", spec=spec, fmt=fmt)
        try:
            size_bytes = lifecycle.atomic_save(fig, output_path, dpi=dpi)
        except OSError as e:
            plt.close(fig)
            return envelope.error("output_dir_unwritable", str(e))

        sa = {
            "plotted_min": min(
                (s["plotted_min"] for s in series_stats if s["plotted_min"] is not None),
                default=None),
            "plotted_max": max(
                (s["plotted_max"] for s in series_stats if s["plotted_max"] is not None),
                default=None),
            "nan_fraction": (
                sum(s["nan_fraction"] for s in series_stats) / len(series_stats)
                if series_stats else 0.0),
            "applied_downsample": None,
            "applied_lon_shift": None,
            "applied_clip_pct": None,
            "vmin_used": None, "vmax_used": None,
        }
        ocl = oracle.capture_common(
            fig=fig, tool="render_profile",
            resolved_spec=resolved,
            style_resolution_sources=_sources(spec, trace),
            safety_actions=sa, output_path=output_path,
            output_size_bytes=size_bytes, data_shape=[len(series)])
        ocl["drawn"] = oracle.drawn_for_profile(
            fig=fig, ax=ax, vertical_axis=vertical_axis,
            series_meta=series_meta)
        ocl["style_template_applied"] = oracle.style_template_applied_block(
            template=spec.get("style_template"), trace=trace)
        oracle.finalize(ocl)
        plt.close(fig)

        return envelope.success({
            "output_path": output_path,
            "file_size_bytes": size_bytes,
            "series_count": len(series),
            "series": series_stats,
            "oracle": ocl,
        })
    except Exception as e:
        return envelope.error("internal_render_error",
                              f"{type(e).__name__}: {e}")
