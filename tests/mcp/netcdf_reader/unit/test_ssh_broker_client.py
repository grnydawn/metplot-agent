"""BrokerSFTPClient — JSON-RPC over UNIX socket to a metplot broker.

Tests use a tiny in-process mock server on a temp socket. No
paramiko, no real broker daemon.
"""
from __future__ import annotations

import json
import socket
import threading
from pathlib import Path

import pytest

from src.mcp.netcdf_reader.paths.ssh_broker import (
    BrokerRPCError, BrokerSFTPClient,
)


def _mock_server(sock_path, replies):
    """One-shot per request. Replies is dict {method_name: result_dict_or_error_dict}."""
    Path(sock_path).parent.mkdir(parents=True, exist_ok=True)
    if Path(sock_path).exists():
        Path(sock_path).unlink()
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(sock_path)
    srv.listen(4)
    stop = threading.Event()

    def _loop():
        srv.settimeout(0.2)
        while not stop.is_set():
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                continue
            with conn:
                buf = b""
                while not buf.endswith(b"\n"):
                    c = conn.recv(8192)
                    if not c:
                        break
                    buf += c
                if not buf:
                    continue
                req = json.loads(buf.decode())
                method = req["method"]
                reply_template = replies.get(method)
                if reply_template is None:
                    reply = {"jsonrpc": "2.0", "id": req["id"],
                              "error": {"code": -32601,
                                         "message": f"no mock for {method}"}}
                else:
                    reply = {"jsonrpc": "2.0", "id": req["id"],
                              **reply_template}
                conn.sendall((json.dumps(reply) + "\n").encode())
        srv.close()

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    return stop, t


def test_ping_round_trip(tmp_path):
    sock = str(tmp_path / "b.sock")
    stop, t = _mock_server(sock, {
        "ping": {"result": {"alive": True, "host": "h",
                              "connected_at": "x", "sftp_open": True,
                              "allowed_exec_tools": ["ncdump"]}},
    })
    try:
        c = BrokerSFTPClient(socket_path=sock)
        r = c.ping()
        assert r["alive"] is True
        assert r["host"] == "h"
    finally:
        stop.set(); t.join(timeout=2)


def test_listdir_attr_returns_paramiko_shaped_attrs(tmp_path):
    sock = str(tmp_path / "b.sock")
    stop, t = _mock_server(sock, {
        "listdir": {"result": {"entries": [
            {"name": "a.nc", "size": 10, "mode": 0o100644,
             "mtime": 1.0, "is_dir": False, "is_link": False},
            {"name": "b.nc", "size": 20, "mode": 0o100644,
             "mtime": 2.0, "is_dir": False, "is_link": False},
        ]}},
    })
    try:
        c = BrokerSFTPClient(socket_path=sock)
        attrs = c.listdir_attr("/d")
        assert [a.filename for a in attrs] == ["a.nc", "b.nc"]
        assert attrs[0].st_size == 10
        assert attrs[1].st_size == 20
    finally:
        stop.set(); t.join(timeout=2)


def test_stat_returns_one_attr(tmp_path):
    sock = str(tmp_path / "b.sock")
    stop, t = _mock_server(sock, {
        "stat": {"result": {"entry": {
            "name": "x.nc", "size": 42, "mode": 0o100644,
            "mtime": 5.0, "is_dir": False, "is_link": False}}},
    })
    try:
        c = BrokerSFTPClient(socket_path=sock)
        a = c.stat("/d/x.nc")
        assert a.filename == "x.nc"
        assert a.st_size == 42
    finally:
        stop.set(); t.join(timeout=2)


def test_glob_remote(tmp_path):
    sock = str(tmp_path / "b.sock")
    stop, t = _mock_server(sock, {
        "glob": {"result": {"paths": ["/d/a.nc", "/d/b.nc"]}},
    })
    try:
        c = BrokerSFTPClient(socket_path=sock)
        assert c.glob_remote("/d/*.nc") == ["/d/a.nc", "/d/b.nc"]
    finally:
        stop.set(); t.join(timeout=2)


def test_get_returns_metadata(tmp_path):
    sock = str(tmp_path / "b.sock")
    stop, t = _mock_server(sock, {
        "get_full": {"result": {"bytes_copied": 100, "sha256": "abc"}},
    })
    try:
        c = BrokerSFTPClient(socket_path=sock)
        r = c.get("/remote.nc", "/local.nc")
        assert r == {"bytes_copied": 100, "sha256": "abc"}
    finally:
        stop.set(); t.join(timeout=2)


def test_dump_header(tmp_path):
    sock = str(tmp_path / "b.sock")
    stop, t = _mock_server(sock, {
        "dump_header": {"result": {"cdl": "netcdf foo {...}",
                                     "stderr": "", "exit_code": 0}},
    })
    try:
        c = BrokerSFTPClient(socket_path=sock)
        r = c.dump_header("/path/foo.nc")
        assert r["cdl"].startswith("netcdf")
        assert r["exit_code"] == 0
    finally:
        stop.set(); t.join(timeout=2)


def test_dump_metadata(tmp_path):
    sock = str(tmp_path / "b.sock")
    stop, t = _mock_server(sock, {
        "dump_metadata": {"result": {"ncks_m": "ncks output...",
                                       "stderr": "", "exit_code": 0}},
    })
    try:
        c = BrokerSFTPClient(socket_path=sock)
        r = c.dump_metadata("/path/foo.nc")
        assert "ncks output" in r["ncks_m"]
    finally:
        stop.set(); t.join(timeout=2)


def test_exec_argv(tmp_path):
    sock = str(tmp_path / "b.sock")
    stop, t = _mock_server(sock, {
        "exec": {"result": {"stdout_b64": "aGVsbG8=",  # "hello"
                              "stderr_b64": "", "exit_code": 0}},
    })
    try:
        c = BrokerSFTPClient(socket_path=sock)
        r = c.exec_argv(["ls", "/data"])
        assert r["stdout_b64"] == "aGVsbG8="
        assert r["exit_code"] == 0
    finally:
        stop.set(); t.join(timeout=2)


def test_exec_argv_with_timeout(tmp_path):
    """Verify timeout is passed through in params."""
    sock = str(tmp_path / "b.sock")
    received_params = {}

    def _server_loop():
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        if Path(sock).exists():
            Path(sock).unlink()
        srv.bind(sock)
        srv.listen(1)
        srv.settimeout(2)
        try:
            conn, _ = srv.accept()
        except socket.timeout:
            srv.close(); return
        with conn:
            buf = b""
            while not buf.endswith(b"\n"):
                c = conn.recv(8192)
                if not c:
                    break
                buf += c
            req = json.loads(buf.decode())
            received_params.update(req["params"])
            reply = {"jsonrpc": "2.0", "id": req["id"],
                      "result": {"stdout_b64": "", "stderr_b64": "",
                                  "exit_code": 0}}
            conn.sendall((json.dumps(reply) + "\n").encode())
        srv.close()

    t = threading.Thread(target=_server_loop, daemon=True)
    t.start()
    # Wait for socket to bind
    deadline = __import__("time").time() + 1
    while not Path(sock).exists():
        if __import__("time").time() > deadline:
            raise TimeoutError
        __import__("time").sleep(0.02)
    c = BrokerSFTPClient(socket_path=sock)
    c.exec_argv(["ncdump", "-h", "/x"], timeout=30.0)
    t.join(timeout=3)
    assert received_params.get("timeout") == 30.0


def test_error_response_raises_broker_rpc_error(tmp_path):
    sock = str(tmp_path / "b.sock")
    stop, t = _mock_server(sock, {
        "listdir": {"error": {"code": -32001,
                                "message": "not found: /nope"}},
    })
    try:
        c = BrokerSFTPClient(socket_path=sock)
        with pytest.raises(BrokerRPCError) as ei:
            c.listdir_attr("/nope")
        assert ei.value.code == -32001
        assert "not found" in ei.value.message
    finally:
        stop.set(); t.join(timeout=2)


def test_request_ids_are_unique(tmp_path):
    """Each call uses a fresh increasing id."""
    sock = str(tmp_path / "b.sock")
    stop, t = _mock_server(sock, {
        "ping": {"result": {"alive": True, "host": "h",
                              "connected_at": "x", "sftp_open": True,
                              "allowed_exec_tools": []}},
    })
    try:
        c = BrokerSFTPClient(socket_path=sock)
        c.ping()
        c.ping()
        c.ping()
        # No reliable way to assert IDs are different without snooping;
        # verify the client doesn't crash on repeated calls.
        assert c._req_id == 3
    finally:
        stop.set(); t.join(timeout=2)
