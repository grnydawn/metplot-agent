"""Channel state machine: SFTP → exec → SFTP transition E2E.

After exec_command, the SessionHolder leaves _sftp=None. The next
with_sftp() call must lazily reopen it. We verify this through the
JSON-RPC layer by interleaving listdir / dump_header / ping calls.
"""
from __future__ import annotations

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


def _start_broker(holder, tmp_path):
    sock_path = str(tmp_path / "broker.sock")
    stop = threading.Event()
    t = threading.Thread(
        target=serve_forever,
        kwargs=dict(holder=holder, socket_path=sock_path,
                    stop_event=stop),
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


def test_sftp_to_exec_to_sftp_transition(inproc_sshd, tmp_path):
    holder = _holder(inproc_sshd)
    sock_path, stop, t = _start_broker(holder, tmp_path)
    try:
        # 1. listdir — SFTP open from construction
        r1 = _round_trip(sock_path,
                          {"jsonrpc": "2.0", "id": 1, "method": "listdir",
                           "params": {"path": inproc_sshd.root}})
        assert "result" in r1
        names = {e["name"] for e in r1["result"]["entries"]}
        assert "alpha.nc" in names

        # 2. ping — confirm SFTP currently open
        r2 = _round_trip(sock_path,
                          {"jsonrpc": "2.0", "id": 2, "method": "ping"})
        assert r2["result"]["sftp_open"] is True

        # 3. dump_header — closes SFTP, opens exec, closes exec
        r3 = _round_trip(sock_path,
                          {"jsonrpc": "2.0", "id": 3,
                           "method": "dump_header",
                           "params": {
                               "path": f"{inproc_sshd.root}/alpha.nc"}})
        assert r3["result"]["exit_code"] == 0
        assert "netcdf alpha" in r3["result"]["cdl"]

        # 4. ping — SFTP should now be closed (state = None)
        r4 = _round_trip(sock_path,
                          {"jsonrpc": "2.0", "id": 4, "method": "ping"})
        assert r4["result"]["sftp_open"] is False

        # 5. listdir again — must lazily reopen SFTP
        r5 = _round_trip(sock_path,
                          {"jsonrpc": "2.0", "id": 5, "method": "listdir",
                           "params": {"path": inproc_sshd.root}})
        assert "result" in r5
        names2 = {e["name"] for e in r5["result"]["entries"]}
        assert "alpha.nc" in names2

        # 6. ping — SFTP open again
        r6 = _round_trip(sock_path,
                          {"jsonrpc": "2.0", "id": 6, "method": "ping"})
        assert r6["result"]["sftp_open"] is True
    finally:
        stop.set(); t.join(timeout=5); holder.close()


def test_multiple_exec_calls_in_a_row(inproc_sshd, tmp_path):
    """Two dump_header calls in sequence both work — each one fully
    cycles the channel state."""
    holder = _holder(inproc_sshd)
    sock_path, stop, t = _start_broker(holder, tmp_path)
    try:
        for i, path in enumerate(["alpha.nc", "beta.nc"]):
            r = _round_trip(sock_path,
                             {"jsonrpc": "2.0", "id": 10 + i,
                              "method": "dump_header",
                              "params": {
                                  "path":
                                      f"{inproc_sshd.root}/{path}"}})
            assert r["result"]["exit_code"] == 0
            stem = Path(path).stem
            assert f"netcdf {stem}" in r["result"]["cdl"]
    finally:
        stop.set(); t.join(timeout=5); holder.close()
