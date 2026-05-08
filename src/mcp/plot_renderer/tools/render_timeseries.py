"""⤴ format-agnostic — eligible for _core/ lift."""
from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from src.mcp.plot_renderer import (
    adapter, defaults as _defaults, envelope, lifecycle, oracle, style,
)
from src.mcp.plot_renderer.envelope import WarningCode


class _LowessUnavailable(RuntimeError):
    pass


def _apply_trendline(ax: Any, x_axis: Any, values: np.ndarray, kind: str) -> None:
    """Add a trendline to `ax`. `kind` ∈ {"linear", "lowess"}."""
    if kind == "linear":
        # Convert datetime64 to ordinal seconds for fitting
        if np.issubdtype(np.asarray(x_axis).dtype, np.datetime64):
            x_num = np.asarray(x_axis, dtype="datetime64[s]").astype("float64")
        else:
            x_num = np.asarray(x_axis, dtype="float64")
        finite = np.isfinite(values) & np.isfinite(x_num)
        if finite.sum() < 2:
            return
        coeffs = np.polyfit(x_num[finite], values[finite], 1)
        ax.plot(x_axis, np.polyval(coeffs, x_num),
                color="black", linestyle="--", linewidth=1.0)
    elif kind == "lowess":
        try:
            from scipy.signal import savgol_filter  # type: ignore[import-untyped] # noqa: F401
        except (ImportError, ModuleNotFoundError) as e:
            raise _LowessUnavailable(
                "scipy is required for lowess trendline; install with `uv pip install scipy`"
            ) from e
        # Use savgol as a smooth lowess-like estimate
        from scipy.signal import savgol_filter  # type: ignore[import-untyped]
        n = values.shape[0]
        window = max(5, n // 10)
        if window % 2 == 0:
            window += 1
        if window > n:
            return
        smoothed = savgol_filter(values, window_length=window, polyorder=2,
                                  mode="nearest")
        ax.plot(x_axis, smoothed,
                color="black", linestyle="--", linewidth=1.0)


def _resolve_presentation(resolved: dict[str, Any]) -> dict[str, Any]:
    """Fill in remaining presentation fields with library defaults."""
    out = dict(resolved)
    for k, v in _defaults.LIBRARY_DEFAULTS.items():
        out.setdefault(k, v)
    out.setdefault("colorbar_position", "none")  # timeseries has no colorbar
    return out


def _style_resolution_sources(spec: dict[str, Any], trace: dict[str, Any]) -> dict[str, str]:
    explicit = set(spec.keys())
    applied = set(trace.get("fields_applied", []))
    sources: dict[str, str] = {}
    for field in ("colormap", "colorbar_position", "gridlines",
                  "font_scale", "aspect"):
        if field in explicit and spec[field] is not None:
            sources[field] = "explicit"
        elif field in applied or any(f.startswith(field) for f in applied):
            sources[field] = "style_template"
        else:
            sources[field] = "library_default"
    return sources


def render_timeseries(spec: dict[str, Any]) -> dict[str, Any]:
    """Render a 1D time series (single or multi). See spec §2.2."""
    warnings: list[dict[str, Any]] = []
    try:
        # 1. Spec validation + data normalization
        try:
            series = adapter.normalize_1d_series(spec, axis_name="time")
        except adapter.InvalidSpecError as e:
            return envelope.error("invalid_spec", str(e))

        # 2. Style application
        resolved, trace = style.apply(spec, spec.get("style_template"))
        resolved = _resolve_presentation(resolved)

        # 3. Multi-series color cycle warning
        if len(series) > 10:
            warnings.append(envelope.warn(
                WarningCode.COLOR_CYCLE_EXCEEDED,
                f"{len(series)} series exceeds 10-color default cycle; using tab20",
                {"series_count": len(series)}))

        # 4. Render
        fig, ax = plt.subplots(figsize=(8.0, 4.5))
        if len(series) > 10:
            color_cycle = plt.colormaps["tab20"].colors  # type: ignore[attr-defined]
        else:
            color_cycle = plt.colormaps["tab10"].colors  # type: ignore[attr-defined]
        per_series_meta: list[dict[str, Any]] = []
        per_series_stats: list[dict[str, Any]] = []
        for i, s in enumerate(series):
            color = s.get("color") or color_cycle[i % len(color_cycle)]
            line, = ax.plot(s["axis"], s["values"], label=s["label"],
                             color=color, linestyle="-")
            per_series_meta.append({
                "label": s["label"], "n_points": int(s["values"].shape[0]),
                "color": str(color), "linestyle": "-",
            })
            finite = s["values"][np.isfinite(s["values"])]
            per_series_stats.append({
                "label": s["label"],
                "n_points": int(s["values"].shape[0]),
                "plotted_min": float(finite.min()) if finite.size else None,
                "plotted_max": float(finite.max()) if finite.size else None,
                "nan_fraction": (
                    1.0 - float(finite.size) / float(s["values"].size)
                    if s["values"].size else 0.0),
            })
        if spec.get("title"):
            ax.set_title(spec["title"])
        if spec.get("xlabel"):
            ax.set_xlabel(spec["xlabel"])
        if spec.get("ylabel"):
            ax.set_ylabel(spec["ylabel"])
        if len(series) > 1 or resolved.get("legend_placement") not in (None, "none"):
            ax.legend()
        ax.grid(resolved.get("gridlines") != "none", alpha=0.3)

        # Trendline (per spec §2.2)
        kind = spec.get("trendline")
        if kind in ("linear", "lowess"):
            try:
                # Apply on the first series only when single-series, on each
                # series otherwise (only render once for clarity in MVP: first).
                first = series[0]
                _apply_trendline(ax, first["axis"], first["values"], kind)
            except _LowessUnavailable as e:
                plt.close(fig)
                return envelope.error("trendline_dependency_missing", str(e))

        fig.tight_layout()

        # 5. Output
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
            output_path = lifecycle.auto_name(tool="timeseries", spec=spec, fmt=fmt)

        try:
            size_bytes = lifecycle.atomic_save(fig, output_path, dpi=dpi)
        except OSError as e:
            plt.close(fig)
            return envelope.error("output_dir_unwritable", str(e))

        # 6. Oracle
        sources = _style_resolution_sources(spec, trace)
        sa = {
            "plotted_min": min(
                (s["plotted_min"] for s in per_series_stats if s["plotted_min"] is not None),
                default=None),
            "plotted_max": max(
                (s["plotted_max"] for s in per_series_stats if s["plotted_max"] is not None),
                default=None),
            "nan_fraction": (
                sum(s["nan_fraction"] for s in per_series_stats) / len(per_series_stats)
                if per_series_stats else 0.0),
            "applied_downsample": None,
            "applied_lon_shift": None,
            "applied_clip_pct": None,
            "vmin_used": None, "vmax_used": None,
        }
        ocl = oracle.capture_common(
            fig=fig, tool="render_timeseries",
            resolved_spec=resolved,
            style_resolution_sources=sources,
            safety_actions=sa,
            output_path=output_path,
            output_size_bytes=size_bytes,
            data_shape=[len(series)],
        )
        ocl["drawn"] = oracle.drawn_for_timeseries(
            fig=fig, ax=ax, series_meta=per_series_meta,
            trendline_kind=spec.get("trendline"))
        ocl["style_template_applied"] = oracle.style_template_applied_block(
            template=spec.get("style_template"), trace=trace)
        oracle.finalize(ocl)
        plt.close(fig)

        return envelope.success({
            "output_path": output_path,
            "file_size_bytes": size_bytes,
            "series_count": len(series),
            "series": per_series_stats,
            "oracle": ocl,
        }, warnings=warnings)

    except Exception as e:
        # Catch-all: never let a raw exception escape
        return envelope.error("internal_render_error",
                              f"{type(e).__name__}: {e}")
