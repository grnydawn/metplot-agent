# tests/mcp/netcdf_reader/unit/test_seam.py
"""Verify that ⤴ format-agnostic modules don't import format-specific
modules. When a second adapter (Zarr, GRIB, HDF5) is added in a future
cycle, this test ensures the format-agnostic bundle can be lifted to
_core/ without the lift dragging in NetCDF-specific code."""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest


PKG_ROOT = Path(__file__).resolve().parents[4] / "src" / "mcp" / "netcdf_reader"

# Files marked ⤴ format-agnostic in the spec
AGNOSTIC = {
    "envelope.py", "cache.py", "selectors.py", "lifecycle.py",
    "paths/classify.py", "paths/ssh.py",
    "conventions/cf.py",
    "tools/inspect.py", "tools/resolve_spec.py", "tools/read_slice.py",
    "tools/compute_stats.py", "tools/peek.py", "tools/find.py",
    "tools/transforms.py",
}

# Files known to be format-specific
SPECIFIC = {
    "adapter.py",
    "paths/multi_file.py",
    "conventions/wrf.py", "conventions/roms.py",
}


def _collect_imports(path: Path) -> set[str]:
    src = path.read_text()
    try:
        tree = ast.parse(src, str(path))
    except SyntaxError:
        return set()
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                out.add(n.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                out.add(node.module)
    return out


def test_agnostic_modules_do_not_import_specific_modules():
    """Each ⤴ file must not import from a format-specific module."""
    violations: list[str] = []
    for rel in AGNOSTIC:
        f = PKG_ROOT / rel
        assert f.exists(), f"missing agnostic file: {rel}"
        imports = _collect_imports(f)
        for imp in imports:
            for spec in SPECIFIC:
                spec_module = spec.replace("/", ".").removesuffix(".py")
                if imp.endswith(spec_module):
                    violations.append(f"{rel} imports {imp}")
    if violations:
        pytest.fail("seam violations:\n" + "\n".join(violations))


def test_agnostic_files_have_marker_comment():
    """Each ⤴ file should have the marker comment in the docstring or top."""
    missing: list[str] = []
    for rel in AGNOSTIC:
        f = PKG_ROOT / rel
        text = f.read_text()
        # Check the first 800 chars
        if "⤴" not in text[:800]:
            missing.append(rel)
    if missing:
        pytest.fail(
            f"⤴ marker missing from: {missing}. Add a header comment "
            f"(e.g. '\"\"\"⤴ format-agnostic — eligible for _core/ lift.\"\"\"').",
        )
