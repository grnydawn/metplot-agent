"""Cycle 8 Phase B task 2 — MPAS mesh-history pairing heuristics.

When an MPAS history file is inspected without a sibling mesh file
supplied, the inspect tool must:

  (a) detect the missing geometry (cell dim present, latCell absent), and
  (b) surface it via `AmbiguitySubcode.MESH_PAIRING_REQUIRED`
      ambiguous envelope, listing likely candidate mesh files in
      the same directory.

This file covers the heuristic (`find_mesh_candidates`) and the
envelope shape (inspect → ambiguous on MPAS-history-only).

Cycle-8 spec §1 Phase B success criterion #2; §3.3.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader import envelope
from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.paths.mesh_pair import find_mesh_candidates
from src.mcp.netcdf_reader.tools.inspect import inspect


def _mpas_history_like_dataset(n_cells: int = 12) -> xr.Dataset:
    """History-style MPAS file: has NCells/NEdges/NVertLayers dims
    (uppercase, as cycle-6 dogfooding found), but no latCell/lonCell
    coord vars — those live in the sibling mesh file."""
    rng = np.random.default_rng(0)
    return xr.Dataset(
        {
            "Temperature": (
                ("time", "NCells", "NVertLayers"),
                rng.uniform(-2, 30, (1, n_cells, 4)),
                {"units": "C"},
            ),
            "Salinity": (
                ("time", "NCells", "NVertLayers"),
                rng.uniform(30, 38, (1, n_cells, 4)),
                {"units": "g/kg"},
            ),
        },
        attrs={"source": "MPAS", "core_name": "ocean",
               "model_name": "mpas"},
    )


def _mpas_mesh_like_dataset(n_cells: int = 12) -> xr.Dataset:
    """Mesh-style MPAS file: has nCells (lowercase) + latCell etc."""
    rng = np.random.default_rng(1)
    return xr.Dataset(
        {
            "latCell": (("nCells",),
                        rng.uniform(-np.pi / 2, np.pi / 2, n_cells)),
            "lonCell": (("nCells",),
                        rng.uniform(0, 2 * np.pi, n_cells)),
            "latVertex": (("nVertices",),
                          rng.uniform(-np.pi / 2, np.pi / 2, 20)),
            "lonVertex": (("nVertices",),
                          rng.uniform(0, 2 * np.pi, 20)),
            "verticesOnCell": (("nCells", "maxEdges"),
                               rng.integers(1, 20, (n_cells, 6))),
            "nEdgesOnCell": (("nCells",), np.full(n_cells, 6)),
        },
        attrs={"Conventions": "MPAS", "core_name": "ocean",
               "model_name": "mpas"},
    )


# ────────────────────────────────────────────────────────────────────
# find_mesh_candidates heuristic
# ────────────────────────────────────────────────────────────────────

class TestFindMeshCandidates:
    def test_finds_ocean_mesh_for_ocn_hist(self, tmp_path: Path) -> None:
        """The dogfood case: history file `ocn.hist.0001-02-01_00.00.00.nc`
        with no shared prefix should still find `ocean_mesh.nc`
        via the broader `*_mesh.nc` heuristic."""
        (tmp_path / "ocn.hist.0001-02-01_00.00.00.nc").touch()
        (tmp_path / "ocean_mesh.nc").touch()
        cands = find_mesh_candidates(
            tmp_path / "ocn.hist.0001-02-01_00.00.00.nc")
        assert (tmp_path / "ocean_mesh.nc").resolve() in cands, (
            f"expected ocean_mesh.nc in candidates; got {cands}")

    def test_prefers_exact_prefix_match(self, tmp_path: Path) -> None:
        """If `<basename-stem>_mesh.nc` exists, it should rank above
        a generic `*_mesh.nc` match."""
        (tmp_path / "myrun_mesh.nc").touch()
        (tmp_path / "ocean_mesh.nc").touch()
        (tmp_path / "myrun.hist.2024-01.nc").touch()
        cands = find_mesh_candidates(tmp_path / "myrun.hist.2024-01.nc")
        # myrun_mesh comes from the dotted-prefix walk
        # (myrun.hist.2024-01 → myrun.hist → myrun → myrun_mesh.nc)
        assert cands[0].name == "myrun_mesh.nc", (
            f"expected myrun_mesh.nc first; got {[c.name for c in cands]}")

    def test_includes_init_nc_as_candidate(self, tmp_path: Path) -> None:
        """`init.nc` is the canonical MPAS initial-state filename."""
        (tmp_path / "out.0001-01.nc").touch()
        (tmp_path / "init.nc").touch()
        cands = find_mesh_candidates(tmp_path / "out.0001-01.nc")
        assert (tmp_path / "init.nc").resolve() in cands

    def test_empty_when_no_candidates(self, tmp_path: Path) -> None:
        (tmp_path / "lonely.nc").touch()
        cands = find_mesh_candidates(tmp_path / "lonely.nc")
        assert cands == []

    def test_excludes_self(self, tmp_path: Path) -> None:
        """If the queried file's own name matches the heuristic
        (e.g. `*_mesh.nc`), it shouldn't return itself as a pair."""
        (tmp_path / "my_mesh.nc").touch()
        cands = find_mesh_candidates(tmp_path / "my_mesh.nc")
        assert (tmp_path / "my_mesh.nc").resolve() not in cands, (
            f"self should not be a candidate; got {cands}")

    def test_handles_missing_parent_dir(self, tmp_path: Path) -> None:
        """A non-existent path returns empty rather than raising."""
        cands = find_mesh_candidates(
            tmp_path / "no" / "such" / "dir" / "ghost.nc")
        assert cands == []


# ────────────────────────────────────────────────────────────────────
# AmbiguitySubcode and envelope shape
# ────────────────────────────────────────────────────────────────────

class TestEnvelopeSubcode:
    def test_mesh_pairing_required_subcode_exists(self) -> None:
        """Cycle 8 §3.2 adds a new AmbiguitySubcode."""
        assert hasattr(envelope.AmbiguitySubcode, "MESH_PAIRING_REQUIRED")
        assert envelope.AmbiguitySubcode.MESH_PAIRING_REQUIRED == (
            "mesh_pairing_required")


# ────────────────────────────────────────────────────────────────────
# inspect() emits mesh_pairing_required for MPAS history-only
# ────────────────────────────────────────────────────────────────────

class TestInspectEmitsMeshPairingRequired:
    def test_emits_ambiguous_envelope(self, tmp_path: Path,
                                       monkeypatch) -> None:
        """An MPAS history file with no spatial coords → ambiguous."""
        monkeypatch.chdir(tmp_path)
        _mpas_history_like_dataset().to_netcdf(tmp_path / "hist.nc")
        env = inspect(str(tmp_path / "hist.nc"),
                      adapter=NetCDFAdapter())
        assert env["ok"] is False, (
            f"expected ok=False (ambiguous); got {env!r}")
        assert env["error"]["code"] == "ambiguous"
        assert env["error"]["subcode"] == "mesh_pairing_required"

    def test_lists_candidate_when_mesh_present_in_dir(
        self, tmp_path: Path, monkeypatch,
    ) -> None:
        """If a likely mesh file is in the same dir, the ambiguous
        envelope's candidates list it."""
        monkeypatch.chdir(tmp_path)
        _mpas_history_like_dataset().to_netcdf(tmp_path / "hist.nc")
        _mpas_mesh_like_dataset().to_netcdf(tmp_path / "ocean_mesh.nc")
        env = inspect(str(tmp_path / "hist.nc"),
                      adapter=NetCDFAdapter())
        assert env["ok"] is False
        candidates = env["error"]["candidates"]
        paths = [c["value"] for c in candidates]
        assert any(p.endswith("ocean_mesh.nc") for p in paths), (
            f"expected ocean_mesh.nc among candidates; got {paths}")

    def test_empty_candidates_when_no_sibling(self, tmp_path: Path,
                                                monkeypatch) -> None:
        """If there's no mesh file in the dir, the candidates list is
        empty (or omitted) but the envelope is still ambiguous —
        the user must supply a mesh_path explicitly."""
        monkeypatch.chdir(tmp_path)
        _mpas_history_like_dataset().to_netcdf(tmp_path / "hist.nc")
        env = inspect(str(tmp_path / "hist.nc"),
                      adapter=NetCDFAdapter())
        assert env["ok"] is False
        assert env["error"]["subcode"] == "mesh_pairing_required"
        # Empty candidates list is fine
        assert isinstance(env["error"]["candidates"], list)

    def test_retry_param_is_mesh_path(self, tmp_path: Path,
                                       monkeypatch) -> None:
        """The ambiguous envelope tells the caller which param to
        retry with — mesh_path."""
        monkeypatch.chdir(tmp_path)
        _mpas_history_like_dataset().to_netcdf(tmp_path / "hist.nc")
        env = inspect(str(tmp_path / "hist.nc"),
                      adapter=NetCDFAdapter())
        assert env["error"]["retry_with_param"] == "mesh_path"

    def test_mesh_file_alone_does_NOT_emit_ambiguous(
        self, tmp_path: Path, monkeypatch,
    ) -> None:
        """A mesh-only file (has latCell/lonCell) should return ok=True
        with the unstructured spatial envelope, not ambiguous."""
        monkeypatch.chdir(tmp_path)
        _mpas_mesh_like_dataset().to_netcdf(tmp_path / "mesh.nc")
        env = inspect(str(tmp_path / "mesh.nc"),
                      adapter=NetCDFAdapter())
        assert env["ok"] is True, (
            f"mesh-only file must be plottable on its own; got {env!r}")
        assert env["result"]["spatial"]["coord_kind"] == "unstructured"
