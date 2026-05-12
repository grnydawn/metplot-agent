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
    """Render a 2D lat/lon map. See spec §2.1.

    Cycle-8 §3.4 added an `unstructured` branch: when the spec
    includes a `mesh_path`, values are interpreted as a 1-D
    cell-centered field and the renderer dispatches to the
    unstructured branch. Geometry comes from the mesh file.

    Cycle-9 §3.4 extends the unstructured branch with auto-dispatch:
    MPAS-shaped meshes (uxarray-readable) still flow through the
    Voronoi polygon path; CICE grids (TLAT/TLON on (nj, ni)) flow
    through pcolormesh; EAMxx physics grids (lat[ncol]/lon[ncol])
    flow through scatter. Dycore-axis variables refuse via a
    grid_kind="dycore_spectral" hint in the spec.
    """
    if not _CARTOPY_OK:
        return _cartopy_ambiguity()

    # Cycle 9: dycore-axis variables get an early-exit refusal
    # before we attempt any rendering.
    if spec.get("grid_kind") == "dycore_spectral":
        return envelope.error(
            "unstructured_dycore_unsupported",
            "EAMxx dycore spectral-element variables (elem×gp×gp) "
            "are not plottable in cycle 9; deferred to cycle 10+. "
            "Pick a physics-axis variable (ncol-axis) instead.",
            context={"requested_grid_kind": "dycore_spectral"},
        )

    if spec.get("mesh_path"):
        return _render_unstructured_map(spec)

    warnings: list[dict[str, Any]] = []
    fig = None
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
    finally:
        if fig is not None:
            plt.close(fig)


def _peek_grid_kind(mesh_path: str) -> str:
    """Inspect a mesh/grid file and decide which unstructured render
    path to use.

    Returns one of:
      - "cice"   — TLAT(nj, ni) / TLON(nj, ni) present → pcolormesh.
      - "eamxx"  — lat(ncol) / lon(ncol) 1-D present → scatter.
      - "elm"    — latixy/longxy on gridcell dim → scatter (cycle 13).
      - "cpl"    — any <domain>_lat/<domain>_lon present, where
                   domain ∈ {doma, doml, domo, domi} → scatter
                   (cycle 13).
      - "mpas"   — fallback / uxarray-recognizable Voronoi mesh.
    """
    import xarray as xr  # type: ignore[import-untyped]
    try:
        ds = xr.open_dataset(mesh_path, decode_times=False)
    except (FileNotFoundError, OSError):
        # Defer the error to the MPAS path's open_grid call so the
        # caller gets the cycle-8 `mesh_path_unreadable` envelope.
        return "mpas"
    try:
        if ("TLAT" in ds.variables and "TLON" in ds.variables
                and "nj" in ds.dims and "ni" in ds.dims):
            return "cice"
        # Cycle 13: ELM gridcell scatter. Check before EAMxx because
        # latixy/longxy are ELM-specific; the EAMxx path looks for
        # the more-generic `lat`/`lon`.
        if ("gridcell" in ds.dims
                and "latixy" in ds.variables
                and "longxy" in ds.variables):
            return "elm"
        # Cycle 13: CPL multi-domain. Any of the four prefixes
        # signals coupler.
        for dom in ("doma", "doml", "domo", "domi"):
            if (f"{dom}_lat" in ds.variables
                    and f"{dom}_lon" in ds.variables):
                return "cpl"
        if ("lat" in ds.variables and "lon" in ds.variables
                and ds["lat"].ndim == 1
                and ds["lon"].ndim == 1
                and "ncol" in ds.dims):
            return "eamxx"
        return "mpas"
    finally:
        ds.close()


def _render_unstructured_map(spec: dict[str, Any]) -> dict[str, Any]:
    """Cycle 8 §3.4 + cycle 9 §3.4 — auto-dispatching unstructured
    map renderer.

    Routes by mesh-file shape:
      - CICE (TLAT/TLON on (nj, ni)) → pcolormesh after 2-D reshape.
      - EAMxx physics (lat/lon 1-D on ncol) → scatter.
      - MPAS Voronoi (anything uxarray can read) → polygon fill.
    """
    grid_kind = _peek_grid_kind(spec["mesh_path"])
    if grid_kind == "cice":
        return _render_cice_grid(spec)
    if grid_kind == "eamxx":
        return _render_eamxx_grid(spec)
    # Cycle 13 theme B — ELM/CPL scatter dispatches.
    if grid_kind == "elm":
        return _render_elm_gridcell(spec)
    if grid_kind == "cpl":
        return _render_cpl_domain(spec)
    return _render_mpas_voronoi(spec)


def _render_mpas_voronoi(spec: dict[str, Any]) -> dict[str, Any]:
    """Cycle 8 §3.4 — Voronoi-cell polygon-fill renderer for MPAS
    unstructured meshes. Uses uxarray's `uxgrid.to_polycollection()`
    (Phase A primary library)."""
    try:
        import uxarray as ux
    except ImportError as e:
        return envelope.ambiguous(
            subcode="uxarray_missing",
            message=(
                "uxarray is not installed. Install with "
                "`uv pip install -e '.[cycle8-poc]'` or "
                "`uv pip install uxarray`."),
            candidates=[
                {"param": "install",
                 "value": "uv pip install uxarray",
                 "kind": "shell_command"},
            ],
            retry_with_param=None,
            context={"import_error": str(e)},
        )

    warnings: list[dict[str, Any]] = []
    fig = None
    try:
        mesh_path = spec["mesh_path"]
        try:
            uxgrid = ux.open_grid(mesh_path)
        except (FileNotFoundError, OSError) as e:
            return envelope.error(
                "mesh_path_unreadable",
                f"could not open mesh_path {mesh_path!r}: {e}")

        values = np.asarray(spec.get("values"), dtype="float64")
        if values.ndim != 1:
            return envelope.error(
                "invalid_spec",
                f"unstructured render expects 1-D values; got "
                f"shape {values.shape}")
        if values.shape[0] != uxgrid.n_face:
            return envelope.error(
                "shape_mismatch",
                f"values length {values.shape[0]} != mesh n_face "
                f"{uxgrid.n_face} — wrong mesh for this slice?")

        # Style resolution — mirror the rectilinear path's
        # cmap/projection ambiguity handling so the contract is
        # uniform across rendering branches.
        resolved, trace = style.apply(spec, spec.get("style_template"))
        resolved = _resolve_presentation(resolved)
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

        # Safety pass (subset — auto_downsample / lon_shift don't
        # apply to unstructured input; NaN + constant-field checks do).
        nan = safety.nan_assessment(values)
        if nan["all_nan"]:
            return envelope.ambiguous(
                subcode="all_nan",
                message="every cell is NaN; nothing to plot",
                candidates=[
                    {"param": "time", "value": "different time index"}],
                retry_with_param="time",
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

        # Render. uxgrid.to_polycollection works around the
        # UxDataArray.to_polycollection(cache=False) np.delete bug
        # in v2026.04.1.
        fig = plt.figure(figsize=(8.0, 5.0))
        ax = fig.add_subplot(1, 1, 1, projection=proj)
        cmap = plt.get_cmap(cmap_name).copy()
        cmap.set_bad(alpha=0.0)
        pc = uxgrid.to_polycollection()
        pc.set_array(values)
        pc.set_cmap(cmap)
        pc.set_clim(vmin=vmin, vmax=vmax)
        pc.set_transform(ccrs.PlateCarree())
        pc.set_edgecolor("none")
        ax.add_collection(pc)
        ax.set_global()
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
            orientation = ("horizontal"
                            if cbar_pos in ("top", "bottom")
                            else "vertical")
            cb = fig.colorbar(pc, ax=ax, orientation=orientation,
                              fraction=0.04, pad=0.04)
            if spec.get("colorbar_label"):
                cb.set_label(spec["colorbar_label"])
        if spec.get("title"):
            ax.set_title(spec["title"])
        fig.tight_layout()

        # Output (lifecycle handles atomic-save + dpi clamps).
        fmt = resolved.get("format", "png")
        dpi = int(resolved.get("dpi", 150))
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
            output_path = lifecycle.auto_name(tool="map", spec=spec,
                                                fmt=fmt)
        try:
            size_bytes = lifecycle.atomic_save(fig, output_path,
                                                 dpi=dpi)
        except OSError as e:
            return envelope.error("output_dir_unwritable", str(e))

        # Oracle. Reuse common helpers; tag grid_kind=unstructured
        # on the `drawn` block so audits can tell which renderer
        # produced the figure.
        sa = {
            "plotted_min": (float(np.nanmin(values))
                             if np.isfinite(values).any() else None),
            "plotted_max": (float(np.nanmax(values))
                             if np.isfinite(values).any() else None),
            "nan_fraction": float(nan["nan_fraction"]),
            "applied_downsample": None,
            "applied_lon_shift": False,
            "applied_clip_pct":
                list(clip_pct) if (clip_applied and clip_pct) else
                ([2.0, 98.0] if clip_applied else None),
            "vmin_used": float(vmin),
            "vmax_used": float(vmax),
        }
        ocl = oracle.capture_common(
            fig=fig, tool="render_map",
            resolved_spec=resolved,
            style_resolution_sources=_sources(spec, trace),
            safety_actions=sa, output_path=output_path,
            output_size_bytes=size_bytes,
            data_shape=list(values.shape))
        ocl["drawn"] = oracle.drawn_for_map(
            fig=fig, ax=ax,
            projection_class=proj_name,
            extent=None,
            coastlines_drawn=coastlines_drawn,
            colorbar_label=spec.get("colorbar_label"))
        ocl["drawn"]["grid_kind"] = "unstructured"
        ocl["drawn"]["n_cells"] = int(uxgrid.n_face)
        ocl["drawn"]["mesh_path"] = mesh_path
        ocl["style_template_applied"] = (
            oracle.style_template_applied_block(
                template=spec.get("style_template"), trace=trace))

        return envelope.success({
            "output_path": str(output_path),
            "format": fmt,
            "size_bytes": size_bytes,
            "plotted_min": sa["plotted_min"],
            "plotted_max": sa["plotted_max"],
            "plotted_shape": list(values.shape),
            "applied_downsample": None,
            "applied_lon_shift": False,
            "nan_fraction": sa["nan_fraction"],
            "oracle": ocl,
        }, warnings=warnings)

    except Exception as e:
        return envelope.error("internal_render_error",
                              f"{type(e).__name__}: {e}")
    finally:
        if fig is not None:
            plt.close(fig)


def _common_unstructured_safety_and_style(
    spec: dict[str, Any], values: "np.ndarray",
) -> tuple[
    dict[str, Any], Any, str, float, float, bool, list[dict[str, Any]],
    dict[str, Any], dict[str, Any] | None,
]:
    """Shared style + safety pipeline for the cell-centered unstructured
    branches (CICE + EAMxx). Returns (resolved, proj, cmap_name, vmin,
    vmax, clip_applied, warnings, trace, error_envelope_or_None)."""
    warnings: list[dict[str, Any]] = []
    resolved, trace = style.apply(spec, spec.get("style_template"))
    resolved = _resolve_presentation(resolved)
    cmap_name = resolved.get("colormap", "viridis")
    if not colormap_registry.is_known_cmap(cmap_name):
        return ({}, None, cmap_name, 0.0, 0.0, False, warnings, trace,
                envelope.ambiguous(
                    subcode="unknown_colormap",
                    message=f"unknown colormap: {cmap_name!r}",
                    candidates=[{"param": "colormap", "value": "viridis"},
                                {"param": "colormap", "value": "RdBu_r"}],
                    retry_with_param="colormap",
                    context={"requested": cmap_name}))
    proj_name = resolved.get("projection", "PlateCarree")
    try:
        proj = _make_projection(proj_name)
    except _UnknownProjection:
        return ({}, None, cmap_name, 0.0, 0.0, False, warnings, trace,
                envelope.ambiguous(
                    subcode="unknown_projection",
                    message=f"unknown projection: {proj_name!r}",
                    candidates=[{"param": "projection", "value": p}
                                for p in _PROJECTION_CLASSES],
                    retry_with_param="projection",
                    context={"requested": proj_name}))
    nan = safety.nan_assessment(values)
    if nan["all_nan"]:
        return ({}, None, cmap_name, 0.0, 0.0, False, warnings, trace,
                envelope.ambiguous(
                    subcode="all_nan",
                    message="every cell is NaN; nothing to plot",
                    candidates=[
                        {"param": "time", "value": "different time index"}],
                    retry_with_param="time",
                    context={"nan_fraction": 1.0}))
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
    return (resolved, proj, cmap_name, float(vmin), float(vmax),
            clip_applied, warnings, trace, None)


def _save_and_oracle_unstructured(
    fig: Any, ax: Any, values: "np.ndarray", spec: dict[str, Any],
    resolved: dict[str, Any], trace: dict[str, Any],
    proj_name: str, cmap_name: str, vmin: float, vmax: float,
    clip_applied: bool, warnings: list[dict[str, Any]],
    grid_kind_label: str, n_cells: int, mesh_path: str,
    coastlines_drawn: bool,
) -> dict[str, Any]:
    fmt = resolved.get("format", "png")
    dpi = int(resolved.get("dpi", 150))
    lifecycle.validate_dpi(dpi)
    if spec.get("output_path"):
        try:
            output_path = lifecycle.resolve_output_path(
                spec["output_path"], fmt=spec.get("format"))
        except lifecycle.FormatExtensionMismatch as e:
            return envelope.error("format_extension_mismatch", str(e))
        except lifecycle.UnsupportedFormat as e:
            return envelope.error("unsupported_format", str(e))
        except lifecycle.OutputPathInvalid as e:
            return envelope.error("output_path_invalid", str(e))
    else:
        output_path = lifecycle.auto_name(tool="map", spec=spec, fmt=fmt)
    try:
        size_bytes = lifecycle.atomic_save(fig, output_path, dpi=dpi)
    except OSError as e:
        return envelope.error("output_dir_unwritable", str(e))
    nan_fraction = float(np.isnan(values).sum()) / max(values.size, 1)
    clip_pct = spec.get("clip_pct") or resolved.get("clip_pct")
    sa = {
        "plotted_min": (float(np.nanmin(values))
                        if np.isfinite(values).any() else None),
        "plotted_max": (float(np.nanmax(values))
                        if np.isfinite(values).any() else None),
        "nan_fraction": nan_fraction,
        "applied_downsample": None,
        "applied_lon_shift": False,
        "applied_clip_pct":
            list(clip_pct) if (clip_applied and clip_pct) else
            ([2.0, 98.0] if clip_applied else None),
        "vmin_used": float(vmin),
        "vmax_used": float(vmax),
    }
    ocl = oracle.capture_common(
        fig=fig, tool="render_map",
        resolved_spec=resolved,
        style_resolution_sources=_sources(spec, trace),
        safety_actions=sa, output_path=output_path,
        output_size_bytes=size_bytes,
        data_shape=list(values.shape))
    ocl["drawn"] = oracle.drawn_for_map(
        fig=fig, ax=ax,
        projection_class=proj_name,
        extent=None,
        coastlines_drawn=coastlines_drawn,
        colorbar_label=spec.get("colorbar_label"))
    ocl["drawn"]["grid_kind"] = grid_kind_label
    ocl["drawn"]["n_cells"] = int(n_cells)
    ocl["drawn"]["mesh_path"] = mesh_path
    ocl["style_template_applied"] = (
        oracle.style_template_applied_block(
            template=spec.get("style_template"), trace=trace))
    return envelope.success({
        "output_path": str(output_path),
        "format": fmt,
        "size_bytes": size_bytes,
        "plotted_min": sa["plotted_min"],
        "plotted_max": sa["plotted_max"],
        "plotted_shape": list(values.shape),
        "applied_downsample": None,
        "applied_lon_shift": False,
        "nan_fraction": sa["nan_fraction"],
        "oracle": ocl,
    }, warnings=warnings)


def _render_cice_grid(spec: dict[str, Any]) -> dict[str, Any]:
    """Cycle 9 §3.4 — CICE 2-D-reshape pcolormesh renderer."""
    import xarray as xr  # type: ignore[import-untyped]
    mesh_path = spec["mesh_path"]
    fig = None
    try:
        try:
            mesh_ds = xr.open_dataset(mesh_path, decode_times=False)
        except (FileNotFoundError, OSError) as e:
            return envelope.error(
                "mesh_path_unreadable",
                f"could not open mesh_path {mesh_path!r}: {e}")
        try:
            tlat = np.asarray(mesh_ds["TLAT"].values, dtype="float64")
            tlon = np.asarray(mesh_ds["TLON"].values, dtype="float64")
            g_nj = int(mesh_ds.sizes["nj"])
            g_ni = int(mesh_ds.sizes["ni"])
        finally:
            mesh_ds.close()
        n_cells = g_nj * g_ni
        values = np.asarray(spec.get("values"), dtype="float64").reshape(-1)
        if values.size != n_cells:
            return envelope.error(
                "shape_mismatch",
                f"values length {values.size} != grid nj*ni "
                f"{n_cells} — wrong grid for this slice?")
        values_2d = values.reshape(g_nj, g_ni)

        (resolved, proj, cmap_name, vmin, vmax, clip_applied,
         warnings, trace, early) = (
            _common_unstructured_safety_and_style(spec, values))
        if early is not None:
            return early

        fig = plt.figure(figsize=(8.0, 5.0))
        ax = fig.add_subplot(1, 1, 1, projection=proj)
        cmap = plt.get_cmap(cmap_name).copy()
        cmap.set_bad(alpha=0.0)
        masked = np.ma.masked_invalid(values_2d)
        ax.pcolormesh(
            tlon, tlat, masked,
            transform=ccrs.PlateCarree(),
            cmap=cmap, vmin=vmin, vmax=vmax,
            rasterized=True, shading="auto",
        )
        ax.set_global()
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
            from matplotlib import cm as _cm
            from matplotlib.colors import Normalize
            sm = _cm.ScalarMappable(
                norm=Normalize(vmin=vmin, vmax=vmax), cmap=cmap)
            orientation = ("horizontal"
                            if cbar_pos in ("top", "bottom")
                            else "vertical")
            cb = fig.colorbar(sm, ax=ax, orientation=orientation,
                              fraction=0.04, pad=0.04)
            if spec.get("colorbar_label"):
                cb.set_label(spec["colorbar_label"])
        if spec.get("title"):
            ax.set_title(spec["title"])
        fig.tight_layout()

        proj_name = resolved.get("projection", "PlateCarree")
        return _save_and_oracle_unstructured(
            fig=fig, ax=ax, values=values, spec=spec,
            resolved=resolved, trace=trace,
            proj_name=proj_name, cmap_name=cmap_name,
            vmin=vmin, vmax=vmax, clip_applied=clip_applied,
            warnings=warnings,
            grid_kind_label="unstructured_cice",
            n_cells=n_cells, mesh_path=mesh_path,
            coastlines_drawn=coastlines_drawn,
        )
    except Exception as e:
        return envelope.error("internal_render_error",
                              f"{type(e).__name__}: {e}")
    finally:
        if fig is not None:
            plt.close(fig)


def _render_eamxx_grid(spec: dict[str, Any]) -> dict[str, Any]:
    """Cycle 9 §3.4 — EAMxx physics-grid scatter renderer."""
    import xarray as xr  # type: ignore[import-untyped]
    mesh_path = spec["mesh_path"]
    fig = None
    try:
        try:
            mesh_ds = xr.open_dataset(mesh_path, decode_times=False)
        except (FileNotFoundError, OSError) as e:
            return envelope.error(
                "mesh_path_unreadable",
                f"could not open mesh_path {mesh_path!r}: {e}")
        try:
            lat = np.asarray(mesh_ds["lat"].values, dtype="float64")
            lon = np.asarray(mesh_ds["lon"].values, dtype="float64")
            ncol = int(mesh_ds.sizes["ncol"])
        finally:
            mesh_ds.close()
        values = np.asarray(spec.get("values"), dtype="float64").reshape(-1)
        if values.size != ncol:
            return envelope.error(
                "shape_mismatch",
                f"values length {values.size} != grid ncol {ncol} "
                f"— wrong grid for this slice?")

        (resolved, proj, cmap_name, vmin, vmax, clip_applied,
         warnings, trace, early) = (
            _common_unstructured_safety_and_style(spec, values))
        if early is not None:
            return early

        fig = plt.figure(figsize=(8.0, 5.0))
        ax = fig.add_subplot(1, 1, 1, projection=proj)
        cmap = plt.get_cmap(cmap_name).copy()
        cmap.set_bad(alpha=0.0)
        # Point-size scales down as ncol grows so dense grids don't
        # over-paint.
        if ncol > 200_000:
            point_size = 0.5
        elif ncol > 20_000:
            point_size = 1.0
        else:
            point_size = 4.0
        sc = ax.scatter(
            lon, lat, c=values, s=point_size,
            transform=ccrs.PlateCarree(),
            cmap=cmap, vmin=vmin, vmax=vmax,
            edgecolors="none", marker="s",
        )
        ax.set_global()
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
            orientation = ("horizontal"
                            if cbar_pos in ("top", "bottom")
                            else "vertical")
            cb = fig.colorbar(sc, ax=ax, orientation=orientation,
                              fraction=0.04, pad=0.04)
            if spec.get("colorbar_label"):
                cb.set_label(spec["colorbar_label"])
        if spec.get("title"):
            ax.set_title(spec["title"])
        fig.tight_layout()

        proj_name = resolved.get("projection", "PlateCarree")
        return _save_and_oracle_unstructured(
            fig=fig, ax=ax, values=values, spec=spec,
            resolved=resolved, trace=trace,
            proj_name=proj_name, cmap_name=cmap_name,
            vmin=vmin, vmax=vmax, clip_applied=clip_applied,
            warnings=warnings,
            grid_kind_label="unstructured_eamxx",
            n_cells=ncol, mesh_path=mesh_path,
            coastlines_drawn=coastlines_drawn,
        )
    except Exception as e:
        return envelope.error("internal_render_error",
                              f"{type(e).__name__}: {e}")
    finally:
        if fig is not None:
            plt.close(fig)


def _render_elm_gridcell(spec: dict[str, Any]) -> dict[str, Any]:
    """Cycle 13 theme B — ELM gridcell scatter renderer.

    Reads latixy / longxy on the gridcell dim and scatter-plots
    one value per gridcell. PFT / column-level rendering is out
    of scope (cycle 14+)."""
    import xarray as xr  # type: ignore[import-untyped]
    mesh_path = spec["mesh_path"]
    fig = None
    try:
        try:
            mesh_ds = xr.open_dataset(mesh_path, decode_times=False)
        except (FileNotFoundError, OSError) as e:
            return envelope.error(
                "mesh_path_unreadable",
                f"could not open mesh_path {mesh_path!r}: {e}")
        try:
            lat = np.asarray(mesh_ds["latixy"].values, dtype="float64").reshape(-1)
            lon = np.asarray(mesh_ds["longxy"].values, dtype="float64").reshape(-1)
            ngc = int(mesh_ds.sizes["gridcell"])
        finally:
            mesh_ds.close()
        values = np.asarray(spec.get("values"), dtype="float64").reshape(-1)
        if values.size != ngc:
            return envelope.error(
                "shape_mismatch",
                f"values length {values.size} != gridcell {ngc} "
                f"— wrong grid for this slice?")

        (resolved, proj, cmap_name, vmin, vmax, clip_applied,
         warnings, trace, early) = (
            _common_unstructured_safety_and_style(spec, values))
        if early is not None:
            return early

        fig = plt.figure(figsize=(8.0, 5.0))
        ax = fig.add_subplot(1, 1, 1, projection=proj)
        cmap = plt.get_cmap(cmap_name).copy()
        cmap.set_bad(alpha=0.0)
        if ngc > 100_000:
            point_size = 0.5
        elif ngc > 10_000:
            point_size = 1.0
        else:
            point_size = 6.0
        sc = ax.scatter(
            lon, lat, c=values, s=point_size,
            transform=ccrs.PlateCarree(),
            cmap=cmap, vmin=vmin, vmax=vmax,
            edgecolors="none", marker="s",
        )
        ax.set_global()
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
            orientation = ("horizontal"
                            if cbar_pos in ("top", "bottom")
                            else "vertical")
            cb = fig.colorbar(sc, ax=ax, orientation=orientation,
                              fraction=0.04, pad=0.04)
            if spec.get("colorbar_label"):
                cb.set_label(spec["colorbar_label"])
        if spec.get("title"):
            ax.set_title(spec["title"])
        fig.tight_layout()

        proj_name = resolved.get("projection", "PlateCarree")
        return _save_and_oracle_unstructured(
            fig=fig, ax=ax, values=values, spec=spec,
            resolved=resolved, trace=trace,
            proj_name=proj_name, cmap_name=cmap_name,
            vmin=vmin, vmax=vmax, clip_applied=clip_applied,
            warnings=warnings,
            grid_kind_label="unstructured_elm",
            n_cells=ngc, mesh_path=mesh_path,
            coastlines_drawn=coastlines_drawn,
        )
    except Exception as e:
        return envelope.error("internal_render_error",
                              f"{type(e).__name__}: {e}")
    finally:
        if fig is not None:
            plt.close(fig)


def _render_cpl_domain(spec: dict[str, Any]) -> dict[str, Any]:
    """Cycle 13 theme B — CPL single-domain scatter renderer.

    Reads <domain>_lat / <domain>_lon for the requested CPL
    domain prefix (`doma` default, or `doml`/`domo`/`domi`).
    Multi-domain overlay is out of scope (cycle 14+)."""
    import xarray as xr  # type: ignore[import-untyped]
    mesh_path = spec["mesh_path"]
    domain = spec.get("domain", "doma")
    fig = None
    try:
        try:
            mesh_ds = xr.open_dataset(mesh_path, decode_times=False)
        except (FileNotFoundError, OSError) as e:
            return envelope.error(
                "mesh_path_unreadable",
                f"could not open mesh_path {mesh_path!r}: {e}")
        try:
            lat_v = f"{domain}_lat"
            lon_v = f"{domain}_lon"
            if (lat_v not in mesh_ds.variables
                    or lon_v not in mesh_ds.variables):
                return envelope.error(
                    "invalid_spec",
                    f"CPL domain {domain!r} not found in mesh: "
                    f"{lat_v}/{lon_v} missing. Available domains: "
                    f"{sorted({str(k).split('_', 1)[0] for k in mesh_ds.variables if str(k).endswith('_lat')})}")
            lat = np.asarray(mesh_ds[lat_v].values, dtype="float64").reshape(-1)
            lon = np.asarray(mesh_ds[lon_v].values, dtype="float64").reshape(-1)
            ncells = lat.size
        finally:
            mesh_ds.close()
        values = np.asarray(spec.get("values"), dtype="float64").reshape(-1)
        if values.size != ncells:
            return envelope.error(
                "shape_mismatch",
                f"values length {values.size} != domain {domain!r} "
                f"cell count {ncells}")

        (resolved, proj, cmap_name, vmin, vmax, clip_applied,
         warnings, trace, early) = (
            _common_unstructured_safety_and_style(spec, values))
        if early is not None:
            return early

        fig = plt.figure(figsize=(8.0, 5.0))
        ax = fig.add_subplot(1, 1, 1, projection=proj)
        cmap = plt.get_cmap(cmap_name).copy()
        cmap.set_bad(alpha=0.0)
        if ncells > 100_000:
            point_size = 0.5
        elif ncells > 10_000:
            point_size = 1.0
        else:
            point_size = 6.0
        sc = ax.scatter(
            lon, lat, c=values, s=point_size,
            transform=ccrs.PlateCarree(),
            cmap=cmap, vmin=vmin, vmax=vmax,
            edgecolors="none", marker="s",
        )
        ax.set_global()
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
            orientation = ("horizontal"
                            if cbar_pos in ("top", "bottom")
                            else "vertical")
            cb = fig.colorbar(sc, ax=ax, orientation=orientation,
                              fraction=0.04, pad=0.04)
            if spec.get("colorbar_label"):
                cb.set_label(spec["colorbar_label"])
        if spec.get("title"):
            ax.set_title(spec["title"])
        fig.tight_layout()

        proj_name = resolved.get("projection", "PlateCarree")
        return _save_and_oracle_unstructured(
            fig=fig, ax=ax, values=values, spec=spec,
            resolved=resolved, trace=trace,
            proj_name=proj_name, cmap_name=cmap_name,
            vmin=vmin, vmax=vmax, clip_applied=clip_applied,
            warnings=warnings,
            grid_kind_label="unstructured_cpl",
            n_cells=ncells, mesh_path=mesh_path,
            coastlines_drawn=coastlines_drawn,
        )
    except Exception as e:
        return envelope.error("internal_render_error",
                              f"{type(e).__name__}: {e}")
    finally:
        if fig is not None:
            plt.close(fig)
