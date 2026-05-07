# tests/mcp/netcdf_reader/unit/test_ssh_inspect.py
import time
from unittest.mock import MagicMock, patch

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.paths.ssh import AuthAttempt, SSHAuthNeeded, SSHConfig
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


def test_ssh_inspect_returns_ambiguity_when_silent_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = SSHConfig(host="hpc.example.org", port=22, user="u")
    err = SSHAuthNeeded(cfg=cfg, attempts=[
        AuthAttempt("ssh_agent", "skipped", "no SSH_AUTH_SOCK"),
        AuthAttempt("default_identity_files", "no_keys"),
    ])
    with patch("src.mcp.netcdf_reader.paths.ssh.silent_auth_chain",
               side_effect=err):
        env = inspect("ssh://hpc.example.org/data.nc",
                      adapter=NetCDFAdapter())
    assert env["ok"] is False
    assert env["error"]["code"] == "ambiguous"
    assert env["error"]["subcode"] == "ssh_auth_needed"
    cands = env["error"]["candidates"]
    assert any(c["param"] == "identity_file" for c in cands)
    assert any(c["param"] == "password" and c["sensitive"] is True for c in cands)
    assert env["error"]["retry_with_param"] == "ssh_config"
    assert env["error"]["context"]["host"] == "hpc.example.org"
    assert env["error"]["context"]["user"] == "u"
    assert "tried" in env["error"]["context"]


def test_ssh_inspect_handles_auth_failed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.mcp.netcdf_reader.paths.ssh import SSHAuthFailed
    with patch("src.mcp.netcdf_reader.paths.ssh.silent_auth_chain",
               side_effect=SSHAuthFailed("denied")):
        env = inspect("ssh://hpc.example.org/data.nc",
                      adapter=NetCDFAdapter())
    assert env["ok"] is False
    # silent chain failure raised SSHAuthFailed (rare); should still be
    # converted to ssh_auth_needed envelope so the user can retry.
    assert env["error"]["code"] in ("ambiguous", "ssh_auth_failed")


def test_ssh_inspect_retry_with_explicit_ssh_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_client = MagicMock()
    fake_handle = MagicMock()
    with patch("src.mcp.netcdf_reader.paths.ssh.connect_explicit",
               return_value=fake_client) as ce, \
         patch("src.mcp.netcdf_reader.paths.ssh.open_sftp_file",
               return_value=fake_handle), \
         patch("xarray.open_dataset",
               return_value=_make_synthetic_dataset()):
        env = inspect(
            "ssh://hpc.example.org/data.nc",
            adapter=NetCDFAdapter(),
            ssh_config={
                "user": "u", "host": "hpc.example.org", "port": 22,
                "auth": {"method": "password", "password": "secret"},
            },
        )
    assert env["ok"] is True
    # connect_explicit was called instead of silent_auth_chain
    ce.assert_called_once()


def test_slow_remote_read_emits_warning(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_client = MagicMock()
    fake_handle = MagicMock()
    def slow_open(*args, **kwargs):
        time.sleep(0)  # we'll patch the timer instead
        return _make_synthetic_dataset()
    with patch("src.mcp.netcdf_reader.paths.ssh.silent_auth_chain",
               return_value=(fake_client, [])), \
         patch("src.mcp.netcdf_reader.paths.ssh.open_sftp_file",
               return_value=fake_handle), \
         patch("xarray.open_dataset", side_effect=slow_open), \
         patch("time.monotonic", side_effect=[0.0, 35.0, 35.0, 35.0]):
        env = inspect("ssh://hpc.example.org/x.nc",
                      adapter=NetCDFAdapter())
    assert env["ok"] is True
    assert any(w["code"] == "slow_remote_read" for w in env["warnings"])
