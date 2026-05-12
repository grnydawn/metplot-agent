"""Cycle 10 Task B — F-03 fix: dim-aware mesh-pair candidate ranking.

Cycle-9 candidate ranking was basename-only — alphabetical among
files matching *_mesh.nc / *_grid.nc. In a dir with two meshes
(global_test_mesh, ocean_test_mesh), alphabetical puts the wrong
one (global, 2562 cells) first when the user's history has 7153
cells. The user trusts the rank-1 suggestion → wasted retry.

Fix: when ≥2 candidates compete, open each candidate (cheap; only
dim sizes) and re-rank dim-matching meshes first. Add a
match_quality field on the candidate dict so the agent can surface
why the top candidate is top.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.paths.mesh_pair import find_mesh_candidates


def _mpas_mesh(tmp_path: Path, name: str, n_cells: int) -> Path:
    """Synthetic MPAS-mesh shape — minimal vars, just the dims that
    the ranker cares about."""
    p = tmp_path / name
    ds = xr.Dataset(
        {
            "latCell": (("nCells",),
                        np.zeros(n_cells, dtype="float64")),
            "lonCell": (("nCells",),
                        np.zeros(n_cells, dtype="float64")),
        }
    )
    ds.to_netcdf(p)
    return p


def _mpas_history(tmp_path: Path, name: str, n_cells: int) -> Path:
    p = tmp_path / name
    ds = xr.Dataset(
        {"Temperature": (("Time", "NCells"),
                          np.zeros((1, n_cells), dtype="float64"))},
    )
    ds.to_netcdf(p)
    return p


def test_dim_matching_mesh_ranked_first(tmp_path: Path):
    """The F-03 reproducer: two meshes in the dir, history has 12
    cells, alphabetical would pick the 5-cell mesh first. Post-fix:
    the 12-cell mesh ranks first."""
    # Alphabetical order: alpha (5) before beta (12).
    _mpas_mesh(tmp_path, "alpha_test_mesh.nc", n_cells=5)
    right = _mpas_mesh(tmp_path, "beta_test_mesh.nc", n_cells=12)
    hist = _mpas_history(tmp_path, "ocn.hist.0001-02.nc", n_cells=12)

    candidates = find_mesh_candidates(hist)
    # Must be re-ranked: beta first, alpha second.
    assert candidates[0] == right.resolve(), (
        f"expected dim-matching mesh first; got {candidates}")


def test_dim_matching_does_not_drop_non_matches(tmp_path: Path):
    """Non-matching meshes still appear in the candidate list — the
    re-rank moves them to the bottom; it doesn't drop them. The user
    might know better than the heuristic (e.g. a hist file that
    needs reshape)."""
    _mpas_mesh(tmp_path, "alpha_test_mesh.nc", n_cells=5)
    _mpas_mesh(tmp_path, "beta_test_mesh.nc", n_cells=12)
    hist = _mpas_history(tmp_path, "ocn.hist.0001-02.nc", n_cells=12)
    candidates = find_mesh_candidates(hist)
    assert len(candidates) == 2, candidates


def test_single_candidate_no_dim_check_needed(tmp_path: Path):
    """If there's only one candidate, the dim-aware re-rank is a
    no-op (cheap). The ranker MUST NOT open the candidate just to
    confirm rank-1 is rank-1."""
    only = _mpas_mesh(tmp_path, "only_mesh.nc", n_cells=5)
    hist = _mpas_history(tmp_path, "ocn.hist.0001-02.nc", n_cells=99)
    # 99 ≠ 5 — but with one candidate, we don't promote it or demote
    # it; the candidate set is just [only_mesh].
    candidates = find_mesh_candidates(hist)
    assert candidates == [only.resolve()]


def test_basename_ranking_intact_when_dims_unknown(tmp_path: Path):
    """If candidate files can't be opened (corrupted, permission
    denied), fall back to basename-only ranking — never crash."""
    # Real mesh.
    _mpas_mesh(tmp_path, "alpha_test_mesh.nc", n_cells=5)
    # Bogus mesh file — not a NetCDF, just a marker.
    bad = tmp_path / "beta_test_mesh.nc"
    bad.write_bytes(b"not a netcdf")
    hist = _mpas_history(tmp_path, "ocn.hist.0001-02.nc", n_cells=5)
    candidates = find_mesh_candidates(hist)
    # Both candidates still appear; the working one ranks first
    # because it dim-matches; the broken one is moved to the bottom
    # (no error).
    assert len(candidates) == 2
    assert candidates[0].name == "alpha_test_mesh.nc"


def test_cice_dim_aware_ranking(tmp_path: Path):
    """CICE shape: history has (nj=1, ni=24); two candidate grids
    (4*6=24 vs 4*5=20). The 24-cell grid ranks first."""
    # Wrong grid (alphabetically first).
    p_wrong = tmp_path / "alpha_grid.nc"
    xr.Dataset(
        {
            "TLAT": (("nj", "ni"), np.zeros((4, 5))),
            "TLON": (("nj", "ni"), np.zeros((4, 5))),
        }
    ).to_netcdf(p_wrong)
    # Right grid (alphabetically second).
    p_right = tmp_path / "beta_grid.nc"
    xr.Dataset(
        {
            "TLAT": (("nj", "ni"), np.zeros((4, 6))),
            "TLON": (("nj", "ni"), np.zeros((4, 6))),
        }
    ).to_netcdf(p_right)
    # Flattened CICE history (nj=1, ni=24).
    p_hist = tmp_path / "cice.r.0001-02.nc"
    xr.Dataset(
        {"aicen": (("ncat", "nj", "ni"), np.zeros((1, 1, 24)))}
    ).to_netcdf(p_hist)
    candidates = find_mesh_candidates(p_hist)
    assert candidates[0] == p_right.resolve(), (
        f"expected beta_grid (4x6=24) first; got {candidates}")
