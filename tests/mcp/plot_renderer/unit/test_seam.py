# tests/mcp/plot_renderer/unit/test_seam.py
"""Enforce the format-agnostic + cartopy-isolation seam discipline.

Files marked ⤴ format-agnostic must NOT import:
- NetCDF / HDF5 / Zarr / GRIB libraries (input formats)
- The cycle-1 package (loose coupling rule)

Only `slice_loader.py` (which sets __format_specific__ = True) may
import h5netcdf / netCDF4 / xarray's NetCDF engine paths.

Only `tools/render_map.py` may import cartopy.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest


_FORMAT_BANNED = {"netCDF4", "h5netcdf", "cftime", "pynio", "cfgrib", "zarr"}
_CYCLE1_BANNED = "src.mcp.netcdf_reader"
_CARTOPY_NAMES = {"cartopy", "cartopy.crs", "cartopy.feature"}

_PACKAGE_ROOT = Path(__file__).resolve().parents[4] / "src" / "mcp" / "plot_renderer"


def _python_files() -> list[Path]:
    return sorted(p for p in _PACKAGE_ROOT.rglob("*.py")
                  if "__pycache__" not in p.parts)


def _is_format_specific_module(path: Path) -> bool:
    src = path.read_text()
    return "__format_specific__ = True" in src


def _is_cartopy_aware_module(path: Path) -> bool:
    return path.name == "render_map.py"


def _imports_in(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                out.add(n.name.split(".")[0])
                out.add(n.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                out.add(node.module.split(".")[0])
                out.add(node.module)
    return out


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: p.name)
def test_format_agnostic_no_format_imports(path: Path) -> None:
    if _is_format_specific_module(path):
        pytest.skip("format-specific module — exempt")
    imports = _imports_in(path)
    banned_hits = imports & _FORMAT_BANNED
    assert not banned_hits, (
        f"{path.name} (format-agnostic) imports format-specific libs: "
        f"{sorted(banned_hits)}")


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: p.name)
def test_no_cycle1_import(path: Path) -> None:
    imports = _imports_in(path)
    for imp in imports:
        assert _CYCLE1_BANNED not in imp, (
            f"{path.name} imports cycle-1's package: {imp}; "
            f"contracts must be JSON shapes only")


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: p.name)
def test_cartopy_isolation(path: Path) -> None:
    if _is_cartopy_aware_module(path):
        return
    imports = _imports_in(path)
    cartopy_hits = imports & _CARTOPY_NAMES
    assert not cartopy_hits, (
        f"{path.name} imports cartopy outside tools/render_map.py: "
        f"{sorted(cartopy_hits)}")
