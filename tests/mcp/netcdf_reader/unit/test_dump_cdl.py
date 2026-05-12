"""Cycle 12 task 3 — dump_cdl (ncks --cdl parity).

dump_cdl(path, *, variables=None, header_only=False) returns a
JSON envelope with result.cdl containing CDL text. CDL is the
textual representation of NetCDF metadata + data that
ncdump / ncks --cdl produces.

These unit tests pin the structural content of our CDL:
- top-level "netcdf <name> {" / "}" wrapper
- "dimensions:" block with `name = size ;` lines
- "variables:" block with type+dims+attrs
- "// global attributes:" block
- "data:" block (omitted when header_only=True)
- variables filter (a la ncks -v)

The bit-exact-vs-ncks comparison lives in test_ncks_parity.py.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.dump_cdl import dump_cdl


def _fixture(tmp_path: Path) -> Path:
    """Small mixed-type fixture."""
    ds = xr.Dataset(
        {
            "T": (("time", "lat"),
                  np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]],
                            dtype="float64"),
                  {"units": "K", "long_name": "temperature"}),
            "flag": (("time",),
                     np.array([0, 1], dtype="int32"),
                     {"description": "binary flag"}),
        },
        coords={
            "time": np.array([100, 200], dtype="int64"),
            "lat": np.array([-45.0, 0.0, 45.0], dtype="float64"),
        },
        attrs={"Conventions": "CF-1.7", "title": "test"},
    )
    p = tmp_path / "cdl.nc"
    ds.to_netcdf(p)
    return p


def test_cdl_has_top_level_wrapper(tmp_path: Path):
    p = _fixture(tmp_path)
    env = dump_cdl(str(p), adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")
    cdl = env["result"]["cdl"]
    assert cdl.startswith("netcdf ")
    assert cdl.rstrip().endswith("}")
    assert "{" in cdl.splitlines()[0]


def test_cdl_dimensions_block(tmp_path: Path):
    p = _fixture(tmp_path)
    env = dump_cdl(str(p), adapter=NetCDFAdapter())
    cdl = env["result"]["cdl"]
    assert "dimensions:" in cdl
    # Dim sizes appear as `name = size ;`
    assert "time = 2 ;" in cdl
    assert "lat = 3 ;" in cdl


def test_cdl_variables_block(tmp_path: Path):
    p = _fixture(tmp_path)
    env = dump_cdl(str(p), adapter=NetCDFAdapter())
    cdl = env["result"]["cdl"]
    assert "variables:" in cdl
    # CDL type + name + dims
    assert "double T(time, lat) ;" in cdl
    assert "int flag(time) ;" in cdl


def test_cdl_variable_attributes(tmp_path: Path):
    p = _fixture(tmp_path)
    env = dump_cdl(str(p), adapter=NetCDFAdapter())
    cdl = env["result"]["cdl"]
    # Per-variable attributes are spelled `varname:attr = value ;`
    assert 'T:units = "K" ;' in cdl
    assert 'T:long_name = "temperature" ;' in cdl


def test_cdl_global_attributes(tmp_path: Path):
    p = _fixture(tmp_path)
    env = dump_cdl(str(p), adapter=NetCDFAdapter())
    cdl = env["result"]["cdl"]
    assert "// global attributes:" in cdl
    assert ':Conventions = "CF-1.7" ;' in cdl
    assert ':title = "test" ;' in cdl


def test_cdl_data_section_present_by_default(tmp_path: Path):
    p = _fixture(tmp_path)
    env = dump_cdl(str(p), adapter=NetCDFAdapter())
    cdl = env["result"]["cdl"]
    assert "data:" in cdl
    # Variable values appear after data:
    assert " T = " in cdl


def test_cdl_header_only_omits_data(tmp_path: Path):
    p = _fixture(tmp_path)
    env = dump_cdl(str(p), header_only=True, adapter=NetCDFAdapter())
    cdl = env["result"]["cdl"]
    assert "data:" not in cdl
    # But schema content stays.
    assert "variables:" in cdl
    assert "double T(time, lat) ;" in cdl


def test_cdl_variables_filter(tmp_path: Path):
    """variables=['T'] restricts output (parallels ncks -v T --cdl)."""
    p = _fixture(tmp_path)
    env = dump_cdl(str(p), variables=["T"], adapter=NetCDFAdapter())
    cdl = env["result"]["cdl"]
    assert "double T(time, lat) ;" in cdl
    # flag should not appear as a top-level variable line
    assert "int flag(time) ;" not in cdl


def test_cdl_unknown_variable_filter(tmp_path: Path):
    p = _fixture(tmp_path)
    env = dump_cdl(str(p), variables=["not_there"],
                    adapter=NetCDFAdapter())
    assert env["ok"] is False
    assert env["error"]["code"] in ("invalid_spec", "internal_error")


def test_cdl_unknown_file(tmp_path: Path):
    env = dump_cdl(str(tmp_path / "missing.nc"), adapter=NetCDFAdapter())
    assert env["ok"] is False
    assert env["error"]["code"] in ("file_not_found", "internal_error")


def test_cdl_envelope_shape(tmp_path: Path):
    """The envelope follows the standard MCP shape."""
    p = _fixture(tmp_path)
    env = dump_cdl(str(p), adapter=NetCDFAdapter())
    assert env["ok"] is True
    assert "result" in env
    assert "cdl" in env["result"]
    # Reasonable size for a small fixture
    assert isinstance(env["result"]["cdl"], str)
    assert len(env["result"]["cdl"]) > 100
