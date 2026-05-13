"""UNIX-socket server: dispatch JSON-RPC requests over a 0600 socket.

Spins serve_forever in a background thread; connects synthetic
clients via stdlib socket; verifies request → response shape.
holder is mocked (no real paramiko).
"""
from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

from src.ssh_broker.server import _dispatch_one, serve_forever


def _round_trip(sock_path: str, request: dict) -> dict:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.connect(sock_path)
        s.sendall((json.dumps(request) + "\n").encode("utf-8"))
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk
        return json.loads(buf.decode("utf-8"))


def _start_server(tmp_path, holder, **kw):
    sock_path = str(tmp_path / "broker.sock")
    stop = threading.Event()
    t = threading.Thread(
        target=serve_forever,
        kwargs=dict(holder=holder, socket_path=sock_path,
                    stop_event=stop, **kw),
        daemon=True,
    )
    t.start()
    deadline = time.time() + 3
    while not Path(sock_path).exists():
        if time.time() > deadline:
            raise TimeoutError
        time.sleep(0.05)
    return sock_path, stop, t


def _live_holder():
    """A MagicMock holder that simulates the SessionHolder enough
    to satisfy METHODS calls that don't actually touch SFTP."""
    h = MagicMock()
    h.is_alive.return_value = True
    h.host = "h"
    h.user = "u"
    h.connected_at = "2026-05-12T00:00:00+00:00"
    h._sftp = MagicMock()
    return h


# ── ping ───────────────────────────────────────────────────────

def test_server_dispatches_ping(tmp_path):
    holder = _live_holder()
    sock_path, stop, t = _start_server(tmp_path, holder)
    try:
        resp = _round_trip(sock_path,
                            {"jsonrpc": "2.0", "id": 1, "method": "ping",
                             "params": {}})
        assert resp["id"] == 1
        assert resp["result"]["alive"] is True
    finally:
        stop.set()
        t.join(timeout=5)


def test_server_returns_method_not_found(tmp_path):
    holder = _live_holder()
    sock_path, stop, t = _start_server(tmp_path, holder)
    try:
        resp = _round_trip(sock_path,
                            {"jsonrpc": "2.0", "id": 2,
                             "method": "not_a_method"})
        assert resp["id"] == 2
        assert resp["error"]["code"] == -32601
    finally:
        stop.set()
        t.join(timeout=5)


def test_server_returns_connection_lost_when_holder_dead(tmp_path):
    holder = MagicMock()
    holder.is_alive.return_value = False
    sock_path, stop, t = _start_server(tmp_path, holder)
    try:
        resp = _round_trip(sock_path,
                            {"jsonrpc": "2.0", "id": 3, "method": "ping"})
        assert resp["error"]["code"] == -32000
    finally:
        stop.set()
        t.join(timeout=5)


def test_server_handles_invalid_params(tmp_path):
    holder = _live_holder()
    # Force a method that requires a "path" to be called without one.
    sock_path, stop, t = _start_server(tmp_path, holder)
    try:
        resp = _round_trip(sock_path,
                            {"jsonrpc": "2.0", "id": 4,
                             "method": "listdir", "params": {}})
        assert resp["error"]["code"] == -32602
        assert "missing param" in resp["error"]["message"]
    finally:
        stop.set()
        t.join(timeout=5)


def test_server_handles_parse_error(tmp_path):
    holder = _live_holder()
    sock_path, stop, t = _start_server(tmp_path, holder)
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(sock_path)
            s.sendall(b"not json at all\n")
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = s.recv(4096)
                if not chunk:
                    break
                buf += chunk
        resp = json.loads(buf.decode())
        assert resp["error"]["code"] == -32700
    finally:
        stop.set()
        t.join(timeout=5)


# ── Socket lifecycle ───────────────────────────────────────────

def test_server_creates_socket_with_0600(tmp_path):
    holder = _live_holder()
    sock_path, stop, t = _start_server(tmp_path, holder)
    try:
        mode = Path(sock_path).stat().st_mode & 0o777
        assert mode == 0o600
    finally:
        stop.set()
        t.join(timeout=5)


def test_server_creates_parent_dir(tmp_path):
    holder = _live_holder()
    nested = tmp_path / "a" / "b" / "broker.sock"
    stop = threading.Event()
    t = threading.Thread(target=serve_forever,
                          kwargs=dict(holder=holder,
                                      socket_path=str(nested),
                                      stop_event=stop),
                          daemon=True)
    t.start()
    deadline = time.time() + 3
    while not nested.exists():
        if time.time() > deadline:
            raise TimeoutError
        time.sleep(0.05)
    try:
        assert nested.parent.is_dir()
    finally:
        stop.set()
        t.join(timeout=5)


def test_server_unlinks_preexisting_socket(tmp_path):
    """If a stale socket exists at the path, server should rebind."""
    sock_path = str(tmp_path / "broker.sock")
    # Pre-create a stale socket file
    stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stale.bind(sock_path)
    stale.close()
    assert Path(sock_path).exists()

    holder = _live_holder()
    stop = threading.Event()
    t = threading.Thread(target=serve_forever,
                          kwargs=dict(holder=holder, socket_path=sock_path,
                                      stop_event=stop), daemon=True)
    t.start()
    time.sleep(0.5)  # let it bind
    try:
        # Should still work
        resp = _round_trip(sock_path,
                            {"jsonrpc": "2.0", "id": 1, "method": "ping"})
        assert resp["result"]["alive"] is True
    finally:
        stop.set()
        t.join(timeout=5)


def test_server_removes_socket_on_shutdown(tmp_path):
    holder = _live_holder()
    sock_path, stop, t = _start_server(tmp_path, holder)
    assert Path(sock_path).exists()
    stop.set()
    t.join(timeout=5)
    assert not Path(sock_path).exists()


# ── extra_allowed plumbing ─────────────────────────────────────

def test_server_passes_extra_allowed_to_methods(tmp_path):
    """ping() returns BUILTIN_ALLOWLIST | extra_allowed in
    allowed_exec_tools. Verify extras flow through serve_forever
    → _dispatch_one → fn(holder, params, extra_allowed=...)."""
    holder = _live_holder()
    sock_path, stop, t = _start_server(tmp_path, holder,
                                         extra_allowed={"ncks", "find"})
    try:
        resp = _round_trip(sock_path,
                            {"jsonrpc": "2.0", "id": 5, "method": "ping"})
        tools = resp["result"]["allowed_exec_tools"]
        assert "ncks" in tools and "find" in tools
        assert "ncdump" in tools  # built-in still there
    finally:
        stop.set()
        t.join(timeout=5)


# ── _dispatch_one direct ──────────────────────────────────────

def test_dispatch_one_parse_error_does_not_crash():
    holder = _live_holder()
    reply = _dispatch_one(holder, b"garbage")
    obj = json.loads(reply.decode())
    assert obj["error"]["code"] == -32700


def test_dispatch_one_internal_error_for_unknown_exception():
    """If a method raises a non-BrokerError, we return INTERNAL_ERROR."""
    holder = _live_holder()
    # Patch METHODS["ping"] to raise something unexpected.
    from src.ssh_broker.methods import METHODS

    orig = METHODS["ping"]
    METHODS["ping"] = lambda h, p, **kw: (_ for _ in ()).throw(
        RuntimeError("boom"))
    try:
        reply = _dispatch_one(
            holder,
            b'{"jsonrpc":"2.0","id":1,"method":"ping","params":{}}\n')
        obj = json.loads(reply.decode())
        assert obj["error"]["code"] == -32603
        assert "boom" in obj["error"]["message"]
    finally:
        METHODS["ping"] = orig
