# src/mcp/plot_renderer/tools/render_section.py
"""Cycle 13 theme D — cross-section pcolormesh renderer.

Inputs (spec):
  * values:           2-D array [n_samples, n_levels]
  * distances_km:     length n_samples — cumulative arc distance
                       (from `slice_along_section`)
  * vertical_coord:   length n_levels (depth / level index / pressure)
  * title?:           figure title
  * units?:           colorbar units label
  * colormap?:        matplotlib cmap name (default "viridis")
  * vmin?, vmax?:     color range
  * vertical_units?:  "m" / "Pa" / "hPa" / "depth_m" — drives
                       axis-inversion default (ocean depth = top
                       surface, deepening downward).
  * output_path?:     destination PNG (default auto-named)
  * invert_vertical?: bool override

Output (envelope.result):
  * output_path, file_size_bytes
  * shape = [n_samples, n_levels]
  * oracle (standard renderer oracle block + drawn-for-section
    summary)
"""
from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from src.mcp.plot_renderer import (
    defaults as _defaults, envelope, lifecycle, oracle,
)

# Vertical-units that indicate "depth-down" semantics (top of plot
# = sea surface; positive deepening). Pressure / depth alike.
_DEPTH_DOWN_UNITS = {"m", "depth_m", "depth", "Pa", "hPa"}


def render_section(spec: dict[str, Any]) -> dict[str, Any]:
    fig = None
    try:
        values = spec.get("values")
        distances = spec.get("distances_km")
        vertical = spec.get("vertical_coord")
        if values is None or distances is None or vertical is None:
            return envelope.error(
                "invalid_spec",
                "render_section requires `values`, `distances_km`, "
                "and `vertical_coord`")
        arr = np.asarray(values, dtype="float64")
        if arr.ndim != 2:
            return envelope.error(
                "invalid_spec",
                f"`values` must be 2-D [n_samples, n_levels]; got "
                f"shape {arr.shape}")
        dist = np.asarray(distances, dtype="float64").reshape(-1)
        vert = np.asarray(vertical, dtype="float64").reshape(-1)
        if arr.shape[0] != dist.size:
            return envelope.error(
                "shape_mismatch",
                f"values.shape[0]={arr.shape[0]} != len(distances_km)"
                f"={dist.size}")
        if arr.shape[1] != vert.size:
            return envelope.error(
                "shape_mismatch",
                f"values.shape[1]={arr.shape[1]} != len(vertical_coord)"
                f"={vert.size}")

        cmap_name = spec.get("colormap") or "viridis"
        vmin = spec.get("vmin")
        vmax = spec.get("vmax")
        if vmin is None:
            vmin = float(np.nanmin(arr))
        if vmax is None:
            vmax = float(np.nanmax(arr))

        vertical_units = spec.get("vertical_units")
        invert_vertical = spec.get("invert_vertical")
        if invert_vertical is None:
            invert_vertical = (vertical_units in _DEPTH_DOWN_UNITS)

        fig, ax = plt.subplots(figsize=(8.0, 5.0))
        cmap = plt.get_cmap(cmap_name).copy()
        cmap.set_bad(alpha=0.0)
        # pcolormesh wants (Y, X) with values shaped (Y-1, X-1) or
        # broadcast-friendly. Our values are (n_samples, n_levels)
        # → transpose so vertical is rows, distance is cols.
        masked = np.ma.masked_invalid(arr.T)  # (n_levels, n_samples)
        mesh = ax.pcolormesh(
            dist, vert, masked, cmap=cmap,
            vmin=vmin, vmax=vmax, shading="auto", rasterized=True)
        ax.set_xlabel("distance (km)")
        ax.set_ylabel(spec.get("ylabel") or (
            f"vertical ({vertical_units})" if vertical_units else "vertical"))
        if invert_vertical:
            ax.invert_yaxis()
        if spec.get("title"):
            ax.set_title(spec["title"])
        cb = fig.colorbar(mesh, ax=ax, orientation="vertical",
                           fraction=0.04, pad=0.04)
        if spec.get("units"):
            cb.set_label(spec["units"])
        fig.tight_layout()

        fmt = spec.get("format") or _defaults.LIBRARY_DEFAULTS.get(
            "format", "png")
        dpi = int(spec.get("dpi")
                  or _defaults.LIBRARY_DEFAULTS.get("dpi", 150))
        lifecycle.validate_dpi(dpi)
        if spec.get("output_path"):
            try:
                output_path = lifecycle.resolve_output_path(
                    spec["output_path"], fmt=spec.get("format"))
            except lifecycle.FormatExtensionMismatch as e:
                return envelope.error(
                    "format_extension_mismatch", str(e))
            except lifecycle.UnsupportedFormat as e:
                return envelope.error("unsupported_format", str(e))
            except lifecycle.OutputPathInvalid as e:
                return envelope.error("output_path_invalid", str(e))
        else:
            output_path = lifecycle.auto_name(
                tool="section", spec=spec, fmt=fmt)
        try:
            size_bytes = lifecycle.atomic_save(fig, output_path, dpi=dpi)
        except OSError as e:
            return envelope.error("output_dir_unwritable", str(e))

        sa = {
            "plotted_min": float(np.nanmin(arr)),
            "plotted_max": float(np.nanmax(arr)),
            "nan_fraction": float(np.isnan(arr).mean()),
            "applied_downsample": None,
            "applied_lon_shift": None,
            "applied_clip_pct": None,
            "vmin_used": vmin, "vmax_used": vmax,
        }
        resolved = {
            "colormap": cmap_name, "vmin": vmin, "vmax": vmax,
            "colorbar_position": "right",
            "gridlines": "default",
            "font_scale": _defaults.LIBRARY_DEFAULTS.get(
                "font_scale", 1.0),
            "aspect": _defaults.LIBRARY_DEFAULTS.get(
                "aspect", "auto"),
            "vertical_units": vertical_units,
            "invert_vertical": invert_vertical,
        }
        # All 5 required presentation fields need a source. We
        # don't apply style templates yet (cycle 14+), so every
        # field is either "explicit" (user passed it) or
        # "library_default".
        sources = {}
        for f in ("colormap", "colorbar_position", "gridlines",
                   "font_scale", "aspect"):
            sources[f] = ("explicit" if spec.get(f) is not None
                          else "library_default")
        ocl = oracle.capture_common(
            fig=fig, tool="render_section",
            resolved_spec=resolved,
            style_resolution_sources=sources,
            safety_actions=sa, output_path=output_path,
            output_size_bytes=size_bytes,
            data_shape=list(arr.shape))
        ocl["drawn"] = {
            "n_samples": int(arr.shape[0]),
            "n_levels": int(arr.shape[1]),
            "distance_km_total": float(dist[-1]) if dist.size else 0.0,
            "vertical_range": [float(vert.min()), float(vert.max())],
            "cmap_name": cmap_name,
            "invert_vertical": bool(invert_vertical),
        }
        ocl["style_template_applied"] = {
            "template_id": None, "applied_fields": [],
            "ignored_fields": [],
        }
        oracle.finalize(ocl)
        return envelope.success({
            "output_path": output_path,
            "file_size_bytes": size_bytes,
            "shape": list(arr.shape),
            "oracle": ocl,
        })
    except Exception as e:
        return envelope.error("internal_render_error",
                              f"{type(e).__name__}: {e}")
    finally:
        if fig is not None:
            plt.close(fig)
