"""End-to-end broker round-trip via the in-proc paramiko sshd.

Validates the broker daemon as a whole: paramiko + SessionHolder
+ JSON-RPC server + UNIX socket. Each broker method exercised
through a stdlib client.
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


def _round_trip(sock_path: str, req: dict) -> dict:
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


def _start_broker(holder, tmp_path: Path):
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
            raise TimeoutError("broker didn't start")
        time.sleep(0.05)
    return sock_path, stop, t


def _connect_holder(inproc_sshd) -> SessionHolder:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname="127.0.0.1", port=inproc_sshd.port,
                    username="testuser", password="testpass",
                    allow_agent=False, look_for_keys=False)
    return SessionHolder(client=client, host="127.0.0.1", user="testuser")


def test_end_to_end_ping(inproc_sshd, tmp_path):
    holder = _connect_holder(inproc_sshd)
    sock_path, stop, t = _start_broker(holder, tmp_path)
    try:
        r = _round_trip(sock_path,
                         {"jsonrpc": "2.0", "id": 1, "method": "ping"})
        assert r["result"]["alive"] is True
        assert r["result"]["host"] == "127.0.0.1"
        assert r["result"]["sftp_open"] is True
    finally:
        stop.set(); t.join(timeout=5); holder.close()


def test_end_to_end_listdir(inproc_sshd, tmp_path):
    holder = _connect_holder(inproc_sshd)
    sock_path, stop, t = _start_broker(holder, tmp_path)
    try:
        r = _round_trip(sock_path,
                         {"jsonrpc": "2.0", "id": 2, "method": "listdir",
                          "params": {"path": inproc_sshd.root}})
        names = {e["name"] for e in r["result"]["entries"]}
        assert {"alpha.nc", "beta.nc"}.issubset(names)
    finally:
        stop.set(); t.join(timeout=5); holder.close()


def test_end_to_end_glob_nc_only(inproc_sshd, tmp_path):
    holder = _connect_holder(inproc_sshd)
    sock_path, stop, t = _start_broker(holder, tmp_path)
    try:
        r = _round_trip(sock_path,
                         {"jsonrpc": "2.0", "id": 3, "method": "glob",
                          "params": {"pattern": f"{inproc_sshd.root}/*.nc"}})
        paths = r["result"]["paths"]
        assert sorted(Path(p).name for p in paths) == ["alpha.nc", "beta.nc"]
    finally:
        stop.set(); t.join(timeout=5); holder.close()


def test_end_to_end_get_chunk(inproc_sshd, tmp_path):
    holder = _connect_holder(inproc_sshd)
    sock_path, stop, t = _start_broker(holder, tmp_path)
    try:
        r = _round_trip(sock_path,
                         {"jsonrpc": "2.0", "id": 4, "method": "get_chunk",
                          "params": {
                              "path": f"{inproc_sshd.root}/alpha.nc",
                              "offset": 0, "length": 8,
                          }})
        data = base64.b64decode(r["result"]["data_b64"])
        # First 8 bytes are the HDF5 signature seeded by the fixture
        assert data == b"\x89HDF\r\n\x1a\n"
    finally:
        stop.set(); t.join(timeout=5); holder.close()


def test_end_to_end_dump_header(inproc_sshd, tmp_path):
    """The fixture's exec emulator returns a stub CDL starting with
    'netcdf <stem> {'. This proves the full SFTP→exec→SFTP cycle."""
    holder = _connect_holder(inproc_sshd)
    sock_path, stop, t = _start_broker(holder, tmp_path)
    try:
        r = _round_trip(sock_path,
                         {"jsonrpc": "2.0", "id": 5,
                          "method": "dump_header",
                          "params": {
                              "path": f"{inproc_sshd.root}/alpha.nc"}})
        cdl = r["result"]["cdl"]
        assert "netcdf alpha" in cdl
        assert r["result"]["exit_code"] == 0
    finally:
        stop.set(); t.join(timeout=5); holder.close()
