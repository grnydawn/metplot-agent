# tests/mcp/netcdf_reader/unit/test_ssh_inspect.py
from unittest.mock import MagicMock, patch
import xarray as xr
import numpy as np
from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.inspect import inspect


def _make_synthetic_dataset():
    return xr.Dataset(
        {"v": (("time", "lat", "lon"),
               np.zeros((1, 2, 2), dtype="float32"))},
        coords={"time": np.array(["2024-09-01"], dtype="datetime64[D]"),
                "lat": [0.0, 1.0], "lon": [0.0, 1.0]},
        attrs={"Conventions": "CF-1.7"},
    )


def test_ssh_inspect_succeeds_with_silent_auth(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_client = MagicMock()
    fake_handle = MagicMock()

    with patch("src.mcp.netcdf_reader.paths.ssh.silent_auth_chain",
               return_value=(fake_client, [])), \
         patch("src.mcp.netcdf_reader.paths.ssh.open_sftp_file",
               return_value=fake_handle), \
         patch("xarray.open_dataset",
               return_value=_make_synthetic_dataset()):
        env = inspect("ssh://hpc.example.org/data.nc",
                      adapter=NetCDFAdapter())
    assert env["ok"] is True
    assert env["result"]["kind"] == "ssh_remote"
    assert env["result"]["convention"]["primary"] == "CF"
