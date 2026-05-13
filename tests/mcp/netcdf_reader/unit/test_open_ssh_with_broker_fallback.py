"""Discover broker socket; fall back to None if absent.

The MCP uses this to route ssh:// paths through the broker
(when present) or fall through to the cycle-12 paramiko path
(when absent).
"""
from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path

from src.mcp.netcdf_reader.paths.ssh import (
    discover_broker_socket, open_ssh_with_broker_fallback,
)


def test_discover_broker_socket_returns_path_when_present(
    monkeypatch, tmp_path,
):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    sock_dir = tmp_path / "metplot-ssh"
    sock_dir.mkdir()
    sock_path = sock_dir / "h.example.sock"
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(str(sock_path))
    try:
        found = discover_broker_socket("h.example")
        assert found == str(sock_path)
    finally:
        s.close()
        sock_path.unlink(missing_ok=True)


def test_discover_broker_socket_returns_none_when_absent(
    monkeypatch, tmp_path,
):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    assert discover_broker_socket("nope.example") is None


def test_discover_broker_socket_falls_back_to_tmp_when_no_xdg(
    monkeypatch, tmp_path,
):
    """Without XDG_RUNTIME_DIR, looks at /tmp/metplot-ssh/<host>.sock."""
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    # We don't want to actually touch /tmp/metplot-ssh — just verify
    # the function returns None when nothing is there.
    result = discover_broker_socket("not-a-real-host-zzz.example")
    assert result is None


def test_open_ssh_with_broker_fallback_returns_none_no_socket(
    monkeypatch, tmp_path,
):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    assert open_ssh_with_broker_fallback("h.example") is None


def test_open_ssh_with_broker_fallback_returns_client_when_ping_ok(
    monkeypatch, tmp_path,
):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    sock_dir = tmp_path / "metplot-ssh"; sock_dir.mkdir()
    sock_path = str(sock_dir / "h.example.sock")
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(sock_path); srv.listen(1)

    def _reply_once():
        srv.settimeout(2)
        try:
            conn, _ = srv.accept()
        except socket.timeout:
            return
        with conn:
            buf = b""
            while not buf.endswith(b"\n"):
                c = conn.recv(4096)
                if not c: break
                buf += c
            conn.sendall((json.dumps({"jsonrpc": "2.0", "id": 1,
                                        "result": {"alive": True}}) + "\n")
                         .encode())

    th = threading.Thread(target=_reply_once, daemon=True)
    th.start()
    try:
        out = open_ssh_with_broker_fallback("h.example")
        assert out is not None
        assert hasattr(out, "listdir_attr")  # BrokerSFTPClient
    finally:
        srv.close()
        Path(sock_path).unlink(missing_ok=True)
        th.join(timeout=2)


def test_open_ssh_with_broker_fallback_returns_none_on_failed_ping(
    monkeypatch, tmp_path,
):
    """Socket exists but no one's serving — ping fails → return None."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    sock_dir = tmp_path / "metplot-ssh"; sock_dir.mkdir()
    sock_path = str(sock_dir / "h.example.sock")
    # Create the socket file but don't accept/listen.
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(sock_path)
    # Don't listen, so connect will fail.
    try:
        out = open_ssh_with_broker_fallback("h.example")
        assert out is None
    finally:
        srv.close()
        Path(sock_path).unlink(missing_ok=True)
