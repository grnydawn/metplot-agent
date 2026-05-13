"""Socket permission regression — credential-equivalent surface.

The broker UNIX socket is the entry point for the metplot MCP to
issue commands inside the authenticated SSH session. A world- or
group-writable socket would let any local process forge requests
and read remote files. These tests lock the 0600 invariant so a
refactor can't quietly weaken it.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

from src.ssh_broker.server import serve_forever


def _start(holder, sock_path):
    stop = threading.Event()
    t = threading.Thread(
        target=serve_forever,
        kwargs=dict(holder=holder, socket_path=sock_path, stop_event=stop),
        daemon=True,
    )
    t.start()
    deadline = time.time() + 3
    while not Path(sock_path).exists():
        if time.time() > deadline:
            raise TimeoutError("server didn't start")
        time.sleep(0.05)
    return stop, t


def _live_holder():
    h = MagicMock()
    h.is_alive.return_value = True
    return h


def test_socket_mode_is_0600(tmp_path):
    """The socket must be 0600 — owner-only read/write."""
    sock_path = str(tmp_path / "b.sock")
    stop, t = _start(_live_holder(), sock_path)
    try:
        mode = Path(sock_path).stat().st_mode & 0o777
        assert mode == 0o600, (
            f"expected 0600, got {oct(mode)} — credential-equivalent "
            f"surface must NOT be readable/writable beyond owner")
    finally:
        stop.set()
        t.join(timeout=5)


def test_socket_is_not_group_writable(tmp_path):
    """Explicit: defense against an accidentally widened mask."""
    sock_path = str(tmp_path / "b.sock")
    stop, t = _start(_live_holder(), sock_path)
    try:
        st = Path(sock_path).stat()
        assert (st.st_mode & 0o020) == 0, "socket is group-writable"
        assert (st.st_mode & 0o002) == 0, "socket is world-writable"
        assert (st.st_mode & 0o004) == 0, "socket is world-readable"
        assert (st.st_mode & 0o040) == 0, "socket is group-readable"
    finally:
        stop.set()
        t.join(timeout=5)


def test_socket_parent_dir_created_for_nested_path(tmp_path):
    """When socket-dir doesn't yet exist, the broker creates it."""
    nested = tmp_path / "a" / "b" / "c" / "broker.sock"
    stop, t = _start(_live_holder(), str(nested))
    try:
        assert nested.parent.is_dir()
        assert nested.exists()
    finally:
        stop.set()
        t.join(timeout=5)
