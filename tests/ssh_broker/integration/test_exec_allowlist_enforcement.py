"""Exec allowlist enforcement — end-to-end via JSON-RPC + in-proc sshd.

Verifies the read-only contract: argv[0] must be in BUILTIN_ALLOWLIST
or in the broker's --allow-exec extras. Writers (rm, mv, etc.) are
always rejected. Shell metacharacters are quoted, not interpreted.
"""
from __future__ import annotations

import base64
import json
import socket
import threading
import time
from pathlib import Path

import paramiko

from src.ssh_broker.server import serve_forever
from src.ssh_broker.session_holder import SessionHolder


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


def _start_broker(holder, tmp_path, *, extra_allowed=None):
    sock_path = str(tmp_path / "broker.sock")
    stop = threading.Event()
    t = threading.Thread(
        target=serve_forever,
        kwargs=dict(holder=holder, socket_path=sock_path,
                    stop_event=stop, extra_allowed=extra_allowed),
        daemon=True,
    )
    t.start()
    deadline = time.time() + 3
    while not Path(sock_path).exists():
        if time.time() > deadline:
            raise TimeoutError
        time.sleep(0.05)
    return sock_path, stop, t


def _holder(inproc_sshd):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname="127.0.0.1", port=inproc_sshd.port,
                    username="testuser", password="testpass",
                    allow_agent=False, look_for_keys=False)
    return SessionHolder(client=client, host="127.0.0.1", user="testuser")


def test_exec_rm_rejected_no_extras(inproc_sshd, tmp_path):
    holder = _holder(inproc_sshd)
    sock_path, stop, t = _start_broker(holder, tmp_path)
    try:
        r = _round_trip(sock_path,
                         {"jsonrpc": "2.0", "id": 1, "method": "exec",
                          "params": {"argv": ["rm", "-rf", "/"]}})
        assert r["error"]["code"] == -32003
        assert "rm" in r["error"]["message"]
    finally:
        stop.set(); t.join(timeout=5); holder.close()


def test_exec_rm_rejected_even_with_ncks_extras(inproc_sshd, tmp_path):
    """Extras add specific tools; do not affect other writers."""
    holder = _holder(inproc_sshd)
    sock_path, stop, t = _start_broker(holder, tmp_path,
                                          extra_allowed={"ncks"})
    try:
        r = _round_trip(sock_path,
                         {"jsonrpc": "2.0", "id": 2, "method": "exec",
                          "params": {"argv": ["rm", "-rf", "/"]}})
        assert r["error"]["code"] == -32003
    finally:
        stop.set(); t.join(timeout=5); holder.close()


def test_exec_ncks_rejected_no_extras(inproc_sshd, tmp_path):
    holder = _holder(inproc_sshd)
    sock_path, stop, t = _start_broker(holder, tmp_path)
    try:
        r = _round_trip(sock_path,
                         {"jsonrpc": "2.0", "id": 3, "method": "exec",
                          "params": {"argv": [
                              "ncks", "-m",
                              f"{inproc_sshd.root}/alpha.nc"]}})
        assert r["error"]["code"] == -32003
    finally:
        stop.set(); t.join(timeout=5); holder.close()


def test_exec_ncks_accepted_with_extras(inproc_sshd, tmp_path):
    """ncks is allowed via --allow-exec; the in-proc sshd reports
    'command not found' (exit 127) but the broker passes through."""
    holder = _holder(inproc_sshd)
    sock_path, stop, t = _start_broker(holder, tmp_path,
                                          extra_allowed={"ncks"})
    try:
        r = _round_trip(sock_path,
                         {"jsonrpc": "2.0", "id": 4, "method": "exec",
                          "params": {"argv": [
                              "ncks", "-m",
                              f"{inproc_sshd.root}/alpha.nc"]}})
        assert "error" not in r, f"unexpected error: {r.get('error')}"
        assert r["result"]["exit_code"] == 127
        stderr = base64.b64decode(r["result"]["stderr_b64"])
        assert b"ncks" in stderr and b"command not found" in stderr
    finally:
        stop.set(); t.join(timeout=5); holder.close()


def test_exec_ncdump_always_allowed(inproc_sshd, tmp_path):
    holder = _holder(inproc_sshd)
    sock_path, stop, t = _start_broker(holder, tmp_path)
    try:
        r = _round_trip(sock_path,
                         {"jsonrpc": "2.0", "id": 5, "method": "exec",
                          "params": {"argv": [
                              "ncdump", "-h",
                              f"{inproc_sshd.root}/alpha.nc"]}})
        assert "error" not in r
        assert r["result"]["exit_code"] == 0
        stdout = base64.b64decode(r["result"]["stdout_b64"])
        assert b"netcdf alpha" in stdout
    finally:
        stop.set(); t.join(timeout=5); holder.close()


def test_exec_ls_always_allowed(inproc_sshd, tmp_path):
    holder = _holder(inproc_sshd)
    sock_path, stop, t = _start_broker(holder, tmp_path)
    try:
        r = _round_trip(sock_path,
                         {"jsonrpc": "2.0", "id": 6, "method": "exec",
                          "params": {"argv": ["ls", inproc_sshd.root]}})
        assert "error" not in r
        stdout = base64.b64decode(r["result"]["stdout_b64"])
        assert b"alpha.nc" in stdout and b"beta.nc" in stdout
    finally:
        stop.set(); t.join(timeout=5); holder.close()


def test_exec_argv_metacharacters_quoted(inproc_sshd, tmp_path):
    """argv=['ls','>foo'] must not redirect — '>foo' goes to ls as
    a literal arg. ls then complains it doesn't exist. No file
    named 'foo' should appear under inproc_sshd.root."""
    holder = _holder(inproc_sshd)
    sock_path, stop, t = _start_broker(holder, tmp_path)
    try:
        r = _round_trip(sock_path,
                         {"jsonrpc": "2.0", "id": 7, "method": "exec",
                          "params": {"argv": ["ls", ">foo"]}})
        assert "error" not in r
        # The ls emulator treats ">foo" as a path → not found → exit 2.
        assert r["result"]["exit_code"] != 0
        # No file named 'foo' or '>foo' was created in the fixture root.
        assert not (Path(inproc_sshd.root) / "foo").exists()
        assert not (Path(inproc_sshd.root) / ">foo").exists()
    finally:
        stop.set(); t.join(timeout=5); holder.close()


def test_exec_empty_argv_rejected(inproc_sshd, tmp_path):
    holder = _holder(inproc_sshd)
    sock_path, stop, t = _start_broker(holder, tmp_path)
    try:
        r = _round_trip(sock_path,
                         {"jsonrpc": "2.0", "id": 8, "method": "exec",
                          "params": {"argv": []}})
        assert r["error"]["code"] == -32003
    finally:
        stop.set(); t.join(timeout=5); holder.close()
