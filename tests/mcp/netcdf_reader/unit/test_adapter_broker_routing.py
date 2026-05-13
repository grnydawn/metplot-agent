"""adapter.open() routes ssh:// through the broker when present."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import xarray as xr

from src.mcp.netcdf_reader.adapter import NetCDFAdapter


def test_adapter_open_uses_broker_when_present(tmp_path):
    """Broker present → stage locally via broker.get(), open with xarray."""
    a = NetCDFAdapter()
    fake_broker = MagicMock()

    def _fake_get(remote, local):
        # Write a tiny valid NetCDF.
        ds = xr.Dataset({"t": (("x",), [1.0, 2.0])},
                         coords={"x": [10, 20]})
        ds.to_netcdf(local)
        return {"bytes_copied": 100, "sha256": "x"}

    fake_broker.get.side_effect = _fake_get
    with patch("src.mcp.netcdf_reader.paths.ssh."
                "open_ssh_with_broker_fallback",
                return_value=fake_broker) as fallback_mock:
        ds = a.open(["ssh://home.example/path/file.nc"])
        assert isinstance(ds, xr.Dataset)
        assert "t" in ds.data_vars
        fallback_mock.assert_called_with("home.example")
        fake_broker.get.assert_called_once()
        # First arg should be the remote path
        remote_arg = fake_broker.get.call_args[0][0]
        assert remote_arg == "/path/file.nc"


def test_adapter_open_falls_back_to_paramiko_when_no_broker():
    """No broker → existing cycle-12 silent_auth_chain path runs."""
    a = NetCDFAdapter()
    with patch("src.mcp.netcdf_reader.paths.ssh."
                "open_ssh_with_broker_fallback", return_value=None), \
         patch("src.mcp.netcdf_reader.paths.ssh.silent_auth_chain") \
            as auth_mock:
        from src.mcp.netcdf_reader.paths.ssh import SSHAuthNeeded, SSHConfig
        auth_mock.side_effect = SSHAuthNeeded(
            cfg=SSHConfig(host="home.example"), attempts=[])
        try:
            a.open(["ssh://home.example/path/file.nc"])
        except SSHAuthNeeded:
            pass
        # The cycle-12 path WAS attempted.
        auth_mock.assert_called()
