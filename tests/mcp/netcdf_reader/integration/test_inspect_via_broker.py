"""End-to-end: inspect() ssh://path.nc via broker + in-proc sshd.

Uses the inproc_sshd fixture (defined in tests/ssh_broker/conftest.py).
Pytest discovers it via the path lookup — we explicitly request it
via the fixture name.

The fixture's exec emulator returns a stub CDL on `ncdump -h`, so
inspect() lands in the dump_header fast path with source = "dump_header".
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

import paramiko
import pytest

from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.inspect import inspect as _inspect
from src.ssh_broker.server import serve_forever
from src.ssh_broker.session_holder import SessionHolder


# Pull in the inproc_sshd fixture from the ssh_broker conftest.
# Pytest auto-finds conftest.py upward, but for a sibling directory
# we need an explicit import via plugins or fixture name lookup.
# Easiest: declare a pytest_plugins line that references the
# ssh_broker tests' conftest. Actually pytest doesn't allow that.
# Instead: redeclare the fixture by importing the underlying handle
# class and reconstructing it. OR: just put the same fixture body here.
#
# Simplest reliable approach: import the fixture function and re-export.

# Import the fixture so pytest finds it.
from tests.ssh_broker.conftest import inproc_sshd  # noqa: F401,F811


@pytest.fixture
def broker_and_holder(inproc_sshd, tmp_path, monkeypatch):  # noqa: F811
    """Yield (sock_path, holder, server_thread, stop_event) — a running
    broker against the in-proc sshd, with XDG_RUNTIME_DIR pointing
    where discover_broker_socket() will find it."""
    # Connect a real paramiko client to the in-proc sshd.
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname="127.0.0.1", port=inproc_sshd.port,
                    username="testuser", password="testpass",
                    allow_agent=False, look_for_keys=False)
    holder = SessionHolder(client=client, host="127.0.0.1",
                            user="testuser")

    # Steer discover_broker_socket() to look in tmp_path.
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    sock_dir = tmp_path / "metplot-ssh"
    sock_dir.mkdir()
    sock_path = str(sock_dir / "127.0.0.1.sock")

    stop = threading.Event()
    th = threading.Thread(
        target=serve_forever,
        kwargs=dict(holder=holder, socket_path=sock_path,
                    stop_event=stop), daemon=True,
    )
    th.start()
    deadline = time.time() + 3
    while not Path(sock_path).exists():
        if time.time() > deadline:
            raise TimeoutError("broker server didn't bind")
        time.sleep(0.05)

    try:
        yield sock_path, holder
    finally:
        stop.set()
        th.join(timeout=5)
        holder.close()


def test_inspect_uses_dump_header_via_broker(broker_and_holder, inproc_sshd):  # noqa: F811
    """inspect('ssh://127.0.0.1/<root>/alpha.nc') hits the dump_header
    fast path (in-proc sshd emulates `ncdump -h` → stub CDL exit 0).
    Result envelope has source='dump_header'."""
    _ = broker_and_holder  # ensures broker is up
    env = _inspect(adapter=NetCDFAdapter(),
                    path=f"ssh://127.0.0.1{inproc_sshd.root}/alpha.nc")
    assert env["ok"] is True, f"unexpected error: {env.get('error')}"
    assert env["result"]["source"] == "dump_header"
    assert env["result"]["name"] == "alpha"


def test_inspect_returns_broker_required_when_socket_missing(monkeypatch,
                                                              tmp_path):
    """Without a broker running, glob path returns broker_required envelope."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    # Ensure no socket exists at the discovery path
    (tmp_path / "metplot-ssh").mkdir()
    env = _inspect(adapter=NetCDFAdapter(),
                    path="ssh://127.0.0.1/data/*.nc")
    assert env["ok"] is False
    assert env["error"]["subcode"] == "broker_required"


def test_classify_ssh_glob_via_broker_end_to_end(broker_and_holder, inproc_sshd):  # noqa: F811
    """Glob ssh:// URL → classify() returns SSH_MULTI list."""
    from src.mcp.netcdf_reader.paths.classify import classify, PathKind

    _ = broker_and_holder
    cls = classify(f"ssh://127.0.0.1{inproc_sshd.root}/*.nc")
    assert cls.kind == PathKind.SSH_MULTI
    # Fixture seeded alpha.nc + beta.nc
    names = sorted(Path(p.replace("ssh://127.0.0.1", "")).name
                    for p in cls.paths)
    assert "alpha.nc" in names and "beta.nc" in names
