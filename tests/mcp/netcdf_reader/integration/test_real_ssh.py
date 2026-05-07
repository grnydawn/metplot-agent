# tests/mcp/netcdf_reader/integration/test_real_ssh.py
"""Opt-in: run against a real SSH endpoint configured via env vars.

Required env vars:
  NCPLOT_REAL_SSH_HOST          remote hostname or ~/.ssh/config alias
  NCPLOT_REAL_SSH_USER          remote username
  NCPLOT_REAL_SSH_FIXTURE_PATH  absolute path to a small NetCDF on the remote

Optional env vars:
  NCPLOT_REAL_SSH_PORT          (default 22)
  NCPLOT_REAL_SSH_KEY_PATH      identity file (otherwise silent chain is tried)
  NCPLOT_REAL_SSH_PASSWORD      via .env.test (gitignored). Discouraged.
"""
from __future__ import annotations

import os
import re

import pytest

from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.inspect import inspect
from src.mcp.netcdf_reader.tools.read_slice import read_slice


pytestmark = [
    pytest.mark.real_ssh,
    pytest.mark.skipif(
        os.environ.get("NCPLOT_REAL_SSH") != "1",
        reason="set NCPLOT_REAL_SSH=1 to run",
    ),
]


def _ssh_url() -> str:
    host = os.environ["NCPLOT_REAL_SSH_HOST"]
    user = os.environ["NCPLOT_REAL_SSH_USER"]
    port = os.environ.get("NCPLOT_REAL_SSH_PORT", "22")
    path = os.environ["NCPLOT_REAL_SSH_FIXTURE_PATH"]
    return f"ssh://{user}@{host}:{port}{path}"


def _ssh_config_explicit() -> dict | None:
    """Build explicit ssh_config kwarg if NCPLOT_REAL_SSH_KEY_PATH set."""
    if "NCPLOT_REAL_SSH_KEY_PATH" in os.environ:
        return {
            "user": os.environ["NCPLOT_REAL_SSH_USER"],
            "host": os.environ["NCPLOT_REAL_SSH_HOST"],
            "port": int(os.environ.get("NCPLOT_REAL_SSH_PORT", 22)),
            "auth": {"method": "identity_file",
                     "identity_file": os.environ["NCPLOT_REAL_SSH_KEY_PATH"]},
        }
    if "NCPLOT_REAL_SSH_PASSWORD" in os.environ:
        return {
            "user": os.environ["NCPLOT_REAL_SSH_USER"],
            "host": os.environ["NCPLOT_REAL_SSH_HOST"],
            "port": int(os.environ.get("NCPLOT_REAL_SSH_PORT", 22)),
            "auth": {"method": "password",
                     "password": os.environ["NCPLOT_REAL_SSH_PASSWORD"]},
        }
    return None


def test_inspect_real_ssh(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = inspect(_ssh_url(), adapter=NetCDFAdapter(),
                  ssh_config=_ssh_config_explicit())
    assert env["ok"] is True, env
    assert env["result"]["kind"] == "ssh_remote"


def test_read_slice_real_ssh(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env_inspect = inspect(_ssh_url(), adapter=NetCDFAdapter(),
                          ssh_config=_ssh_config_explicit())
    var = env_inspect["result"]["variables"][0]["name"]
    env = read_slice(_ssh_url(), variable=var,
                     adapter=NetCDFAdapter(),
                     ssh_config=_ssh_config_explicit())
    assert env["ok"] is True, env


def test_password_never_appears_in_capsys(capsys, tmp_path, monkeypatch):
    if "NCPLOT_REAL_SSH_PASSWORD" not in os.environ:
        pytest.skip("password not configured")
    monkeypatch.chdir(tmp_path)
    inspect(_ssh_url(), adapter=NetCDFAdapter(),
            ssh_config=_ssh_config_explicit())
    out = capsys.readouterr()
    pw = os.environ["NCPLOT_REAL_SSH_PASSWORD"]
    assert pw not in out.out
    assert pw not in out.err


def test_no_password_in_slice_temp_files(tmp_path, monkeypatch):
    if "NCPLOT_REAL_SSH_PASSWORD" not in os.environ:
        pytest.skip("password not configured")
    monkeypatch.chdir(tmp_path)
    env_inspect = inspect(_ssh_url(), adapter=NetCDFAdapter(),
                          ssh_config=_ssh_config_explicit())
    var = env_inspect["result"]["variables"][0]["name"]
    read_slice(_ssh_url(), variable=var, adapter=NetCDFAdapter(),
               ssh_config=_ssh_config_explicit(),
               max_inline_bytes=1)  # force file form
    pw = os.environ["NCPLOT_REAL_SSH_PASSWORD"]
    for f in (tmp_path / ".ncplot").rglob("*"):
        if f.is_file():
            try:
                content = f.read_bytes()
            except Exception:
                continue
            assert pw.encode() not in content, f"password leaked in {f}"
