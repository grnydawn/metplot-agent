"""FORMAT-SPECIFIC (cartopy-aware): map rendering.

This is the only file in cycle-2 that imports cartopy. The seam test
allows it; other tools must not import cartopy.
"""
from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from src.mcp.plot_renderer import (
    adapter, colormap_registry, defaults as _defaults,
    envelope, lifecycle, oracle, safety, style,
)
from src.mcp.plot_renderer.envelope import WarningCode

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


_PROJECTION_CLASSES = (
    "PlateCarree", "Robinson", "NorthPolarStereo", "SouthPolarStereo",
    "LambertConformal", "Mercator",
)


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


def _resolve_presentation(resolved: dict[str, Any]) -> dict[str, Any]:
    out = dict(resolved)
    for k, v in _defaults.LIBRARY_DEFAULTS.items():
        out.setdefault(k, v)
    return out


def _sources(spec: dict[str, Any], trace: dict[str, Any]) -> dict[str, str]:
    explicit = set(spec.keys())
    applied = set(trace.get("fields_applied", []))
    sources: dict[str, str] = {}
    for field in ("colormap", "projection", "colorbar_position",
                   "gridlines", "font_scale", "aspect"):
        if field in explicit and spec[field] is not None:
            sources[field] = "explicit"
        elif field in applied:
            sources[field] = "style_template"
        else:
            sources[field] = "library_default"
    return sources


def _make_projection(name: str) -> Any:
    if name not in _PROJECTION_CLASSES:
        raise _UnknownProjection(name)
    return getattr(ccrs, name)()


class _UnknownProjection(ValueError):
    pass


def render_map(spec: dict[str, Any]) -> dict[str, Any]:
    """Render a 2D lat/lon map. See spec §2.1."""
    if not _CARTOPY_OK:
        return _cartopy_ambiguity()

    warnings: list[dict[str, Any]] = []
    try:
        # 1. Normalize spec → values, coords, meta
        try:
            values, coords, meta = adapter.normalize_2d_any_form(spec)
        except adapter.InvalidSpecError as e:
            return envelope.error("invalid_spec", str(e))

        if values.size == 0:
            return envelope.ambiguous(
                subcode="empty_slice",
                message="data array has zero cells",
                candidates=[{"param": "region", "value": "non-empty bbox"}],
                retry_with_param="region",
                context={"shape": list(values.shape)},
            )

        # 2. Style
        resolved, trace = style.apply(spec, spec.get("style_template"))
        resolved = _resolve_presentation(resolved)

        # 3. Validate cmap + projection names
        cmap_name = resolved.get("colormap", "viridis")
        if not colormap_registry.is_known_cmap(cmap_name):
            return envelope.ambiguous(
                subcode="unknown_colormap",
                message=f"unknown colormap: {cmap_name!r}",
                candidates=[{"param": "colormap", "value": "viridis"},
                            {"param": "colormap", "value": "RdBu_r"}],
                retry_with_param="colormap",
                context={"requested": cmap_name},
            )
        proj_name = resolved.get("projection", "PlateCarree")
        try:
            proj = _make_projection(proj_name)
        except _UnknownProjection:
            return envelope.ambiguous(
                subcode="unknown_projection",
                message=f"unknown projection: {proj_name!r}",
                candidates=[{"param": "projection", "value": p}
                            for p in _PROJECTION_CLASSES],
                retry_with_param="projection",
                context={"requested": proj_name},
            )

        # 4. Safety pass
        nan = safety.nan_assessment(values)
        if nan["all_nan"]:
            return envelope.ambiguous(
                subcode="all_nan",
                message="every cell is NaN; nothing to plot",
                candidates=[{"param": "region",
                             "value": "non-NaN spatial extent"},
                            {"param": "time", "value": "different time index"}],
                retry_with_param="region",
                context={"nan_fraction": 1.0},
            )
        if nan["high_nan_fraction"]:
            warnings.append(envelope.warn(
                WarningCode.HIGH_NAN_FRACTION,
                f"{nan['nan_fraction']:.0%} of cells are NaN",
                {"nan_fraction": nan["nan_fraction"]}))

        const, const_value = safety.is_constant_field(values)
        if const and const_value is not None:
            warnings.append(envelope.warn(
                WarningCode.CONSTANT_FIELD,
                "field has zero variation",
                {"value": const_value}))

        values, coords["lon"], lon_shifted = safety.maybe_lon_shift(
            values, coords["lon"], target=spec.get("lon_convention"))
        if lon_shifted:
            warnings.append(envelope.warn(
                WarningCode.LON_SHIFT_APPLIED,
                f"longitudes shifted to {spec['lon_convention']}",
                {"target": spec["lon_convention"]}))

        downsample_enabled = (resolved.get("downsample", True) is not False)
        values, coords, ds_action = safety.auto_downsample_2d(
            values, coords, enabled=downsample_enabled)
        if ds_action is not None:
            warnings.append(envelope.warn(
                WarningCode.AUTO_DOWNSAMPLED,
                f"downsampled {ds_action['from_shape']} → {ds_action['to_shape']}",
                ds_action))

        clip_pct = spec.get("clip_pct") or resolved.get("clip_pct")
        clip_pct_tuple = tuple(clip_pct) if clip_pct is not None else None
        vmin, vmax, clip_applied = safety.percentile_clip_if_extreme(
            values,
            vmin=spec.get("vmin"), vmax=spec.get("vmax"),
            clip_pct=clip_pct_tuple,
        )
        if clip_applied:
            warnings.append(envelope.warn(
                WarningCode.PERCENTILE_CLIP_APPLIED,
                f"applied percentile clip [{vmin:.3g}, {vmax:.3g}]",
                {"vmin": vmin, "vmax": vmax}))

        # 5. Render
        fig = plt.figure(figsize=(8.0, 5.0))
        ax = fig.add_subplot(1, 1, 1, projection=proj)
        cmap = plt.get_cmap(cmap_name).copy()
        cmap.set_bad(alpha=0.0)
        masked = np.ma.masked_invalid(values)
        mesh = ax.pcolormesh(
            coords["lon"], coords["lat"], masked,
            transform=ccrs.PlateCarree(),
            cmap=cmap, vmin=vmin, vmax=vmax, rasterized=True,
            shading="auto",
        )
        coastlines_drawn = False
        try:
            ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
            coastlines_drawn = True
        except Exception:
            pass
        if resolved.get("gridlines") != "none":
            ax.gridlines(draw_labels=False, linewidth=0.3, alpha=0.4)
        cbar_pos = resolved.get("colorbar_position") or "right"
        if cbar_pos != "none":
            orientation = "horizontal" if cbar_pos in ("top", "bottom") else "vertical"
            cb = fig.colorbar(mesh, ax=ax, orientation=orientation, fraction=0.04, pad=0.04)
            if spec.get("colorbar_label"):
                cb.set_label(spec["colorbar_label"])
        if spec.get("title"):
            ax.set_title(spec["title"])
        extent = spec.get("extent")
        if extent:
            ax.set_extent(extent, crs=ccrs.PlateCarree())
        fig.tight_layout()

        # 6. Output
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
            output_path = lifecycle.auto_name(tool="map", spec=spec, fmt=fmt)
        try:
            size_bytes = lifecycle.atomic_save(fig, output_path, dpi=dpi)
        except OSError as e:
            plt.close(fig)
            return envelope.error("output_dir_unwritable", str(e))

        # 7. Oracle
        sa = {
            "plotted_min": float(np.nanmin(values)) if np.isfinite(values).any() else None,
            "plotted_max": float(np.nanmax(values)) if np.isfinite(values).any() else None,
            "nan_fraction": float(nan["nan_fraction"]),
            "applied_downsample": ds_action,
            "applied_lon_shift": lon_shifted,
            "applied_clip_pct": list(clip_pct) if (clip_applied and clip_pct) else
                                 ([2.0, 98.0] if clip_applied else None),
            "vmin_used": float(vmin),
            "vmax_used": float(vmax),
        }
        ocl = oracle.capture_common(
            fig=fig, tool="render_map",
            resolved_spec=resolved,
            style_resolution_sources=_sources(spec, trace),
            safety_actions=sa, output_path=output_path,
            output_size_bytes=size_bytes, data_shape=list(values.shape))
        ocl["drawn"] = oracle.drawn_for_map(
            fig=fig, ax=ax,
            projection_class=proj_name,
            extent=list(extent) if extent else None,
            coastlines_drawn=coastlines_drawn,
            colorbar_label=spec.get("colorbar_label"))
        ocl["style_template_applied"] = oracle.style_template_applied_block(
            template=spec.get("style_template"), trace=trace)
        oracle.finalize(ocl)
        plt.close(fig)

        return envelope.success({
            "output_path": output_path,
            "file_size_bytes": size_bytes,
            "plotted_min": sa["plotted_min"],
            "plotted_max": sa["plotted_max"],
            "plotted_shape": list(values.shape),
            "applied_downsample": ds_action,
            "applied_lon_shift": lon_shifted,
            "nan_fraction": sa["nan_fraction"],
            "oracle": ocl,
        }, warnings=warnings)

    except Exception as e:
        return envelope.error("internal_render_error",
                              f"{type(e).__name__}: {e}")
