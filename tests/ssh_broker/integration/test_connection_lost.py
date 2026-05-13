"""Broker reports CONNECTION_LOST after the underlying SSH transport dies.

Uses a MagicMock holder with is_alive() controlled by a list-flag,
so we can simulate transport death mid-session.
"""
from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

from src.ssh_broker.server import serve_forever


def _round_trip(sock_path, req):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.connect(sock_path)
        s.sendall((json.dumps(req) + "\n").encode("utf-8"))
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(8192)
            if not chunk:
                break
            buf += chunk
    return json.loads(buf.decode("utf-8"))


def _start(holder, tmp_path):
    sock_path = str(tmp_path / "broker.sock")
    stop = threading.Event()
    t = threading.Thread(
        target=serve_forever,
        kwargs=dict(holder=holder, socket_path=sock_path,
                    stop_event=stop), daemon=True,
    )
    t.start()
    deadline = time.time() + 3
    while not Path(sock_path).exists():
        if time.time() > deadline:
            raise TimeoutError
        time.sleep(0.05)
    return sock_path, stop, t


def test_broker_self_exits_after_connection_loss(tmp_path):
    """Per spec §1.6: broker exits within 5 seconds of detected
    connection loss."""
    holder = MagicMock()
    alive = [True]
    holder.is_alive.side_effect = lambda: alive[0]
    holder.host = "h"; holder.user = "u"; holder.connected_at = "x"
    holder._sftp = MagicMock()
    sock_path = str(tmp_path / "broker.sock")
    stop = threading.Event()
    t = threading.Thread(
        target=serve_forever,
        kwargs=dict(holder=holder, socket_path=sock_path,
                    stop_event=stop, poll_interval=0.1), daemon=True,
    )
    t.start()
    # Wait for socket to bind.
    deadline = time.time() + 3
    while not Path(sock_path).exists():
        if time.time() > deadline:
            raise TimeoutError
        time.sleep(0.05)
    # Kill the holder.
    alive[0] = False
    # Server should self-exit within ~5 seconds.
    started = time.time()
    t.join(timeout=5)
    elapsed = time.time() - started
    assert not t.is_alive(), f"server still running after {elapsed:.2f}s"
    assert elapsed < 4.0


def test_connection_lost_after_holder_dies(tmp_path):
    holder = MagicMock()
    alive = [True]
    holder.is_alive.side_effect = lambda: alive[0]
    holder.host = "h"; holder.user = "u"; holder.connected_at = "x"
    holder._sftp = MagicMock()
    sock_path, stop, t = _start(holder, tmp_path)
    try:
        # First call works.
        r1 = _round_trip(sock_path,
                          {"jsonrpc": "2.0", "id": 1, "method": "ping"})
        assert r1["result"]["alive"] is True

        # Simulate transport death.
        alive[0] = False

        # Second call returns CONNECTION_LOST.
        r2 = _round_trip(sock_path,
                          {"jsonrpc": "2.0", "id": 2, "method": "ping"})
        assert r2["error"]["code"] == -32000
        assert "connection" in r2["error"]["message"].lower()
    finally:
        stop.set(); t.join(timeout=5)
