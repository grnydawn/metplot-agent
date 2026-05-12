"""Cycle 10 Task E — real-file integration: multi-file Omega
glob + paired mesh = time-series-ready unstructured envelope.

Cycle-9 §6 deferred "multi-file globbing for unstructured time
series" as cycle 10+. Cycle 10's F-01 fix unblocks it; the
cycle-1 multi_file_combine path then handles the rest.

Skipped unless `data/omega/` is present on disk.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.inspect import inspect

REPO = Path(__file__).resolve().parents[4]
DATA = REPO / "data" / "omega"

# Cycle-10 spec success criterion #2: 12 monthly Omega histories +
# the cross-year Jan 0002 file = 13 files in the glob; the paired
# mesh has 7153 cells; combined envelope reports
# kind=local_multi, unstructured spatial, time.n covering all
# 12 months (or 13 if cross-year file shares dim space).
pytestmark = pytest.mark.skipif(
    not (DATA / "ocean_test_mesh.nc").exists(),
    reason="data/omega/ files not on disk; skip real-file integration",
)


def test_glob_inspect_unblocked_by_f01_fix():
    """Bare glob inspect on 13 monthly Omega histories used to
    raise TypeError from cf.py:extract_time (F-01). Post-fix:
    returns a valid envelope without crashing. The mesh_pairing
    short-circuit applies only to LOCAL_SINGLE; for LOCAL_MULTI
    the user is expected to supply mesh_path explicitly (see the
    paired test below), so bare-glob returns ok=true with
    spatial=null."""
    env = inspect(
        str(DATA / "ocn.hist.000*-*-01_00.00.00.nc"),
        adapter=NetCDFAdapter())
    # The bar this test sets: NO uncaught Python exception. Either
    # ok=true with spatial=null, or ok=false with a structured
    # envelope — both are acceptable. What's NOT acceptable is the
    # cycle-9 behavior (raw TypeError).
    assert isinstance(env, dict)
    assert "ok" in env
    if env.get("ok"):
        # spatial=null is expected; mesh_path needed for geometry.
        assert env["result"].get("spatial") is None
    else:
        # structured ambiguous / error envelope, not raw exception
        assert env["error"].get("code") is not None


def test_paired_glob_yields_combined_envelope():
    """Glob + mesh_path produces a single combined envelope with
    spatial from the mesh and time-concat across all months."""
    env = inspect(
        str(DATA / "ocn.hist.000*-*-01_00.00.00.nc"),
        mesh_path=str(DATA / "ocean_test_mesh.nc"),
        adapter=NetCDFAdapter())
    assert env.get("ok") is True, env.get("error")
    r = env["result"]
    assert r["kind"] == "local_multi"
    # 12 monthly histories + 1 cross-year = 13 files.
    assert len(r["files"]) >= 12
    # Mesh-derived spatial.
    sp = r["spatial"]
    assert sp is not None
    assert sp["coord_kind"] == "unstructured"
    assert sp["n_cells"] == 7153
    # Time concat across all months.
    assert r["time"]["n"] >= 12
