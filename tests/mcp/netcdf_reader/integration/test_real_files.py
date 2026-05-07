# tests/mcp/netcdf_reader/integration/test_real_files.py
"""Opt-in: pinned real-sample integration tests.

Requires running tests/mcp/netcdf_reader/integration/download_samples.sh
once to populate tests/mcp/netcdf_reader/integration/data/.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.inspect import inspect


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("NCPLOT_INTEGRATION") != "1",
        reason="set NCPLOT_INTEGRATION=1 to run",
    ),
]

DATA = Path(__file__).parent / "data"


@pytest.mark.skipif(not (DATA / "wrfout_sample.nc").exists(),
                    reason="run download_samples.sh first")
def test_inspect_real_wrf(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = inspect(str(DATA / "wrfout_sample.nc"), adapter=NetCDFAdapter())
    assert env["ok"] is True
    assert env["result"]["convention"]["primary"] == "WRF"


@pytest.mark.skipif(not (DATA / "era5_t2m_sample.nc").exists(),
                    reason="run download_samples.sh first")
def test_inspect_real_era5(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = inspect(str(DATA / "era5_t2m_sample.nc"), adapter=NetCDFAdapter())
    assert env["ok"] is True
    assert env["result"]["convention"]["primary"] in ("CF", "CMIP")
