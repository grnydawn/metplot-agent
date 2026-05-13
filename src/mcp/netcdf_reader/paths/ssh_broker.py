"""MCP-side client that talks JSON-RPC to a running metplot-ssh-broker.

When the broker socket is present, the MCP uses this class instead of
opening a paramiko transport. The credential stays in the broker
process; we just speak the JSON-RPC protocol over a local UNIX socket.

Exposes:
  - paramiko-compatible: listdir_attr, stat, get  (subset)
  - broker extensions:   glob_remote, dump_header, dump_metadata,
                          exec_argv, ping
"""
from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import Any

from src.ssh_broker.protocol import (
    decode_line, encode_message, make_request,
)


class BrokerRPCError(Exception):
    """Raised when the broker returns a JSON-RPC error response."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


@dataclass
class _LikeSFTPAttributes:
    """Stand-in for paramiko.SFTPAttributes with the fields the MCP uses."""
    filename: str
    st_size: int
    st_mode: int
    st_mtime: float


class BrokerSFTPClient:
    """JSON-RPC client over a local 0600 UNIX socket."""

    def __init__(self, socket_path: str) -> None:
        self.socket_path = socket_path
        self._req_id = 0

    def _call(self, method: str,
               params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._req_id += 1
        req = make_request(self._req_id, method, params)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(self.socket_path)
            s.sendall(encode_message(req))
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = s.recv(8192)
                if not chunk:
                    break
                buf += chunk
        resp = decode_line(buf)
        if "error" in resp:
            err = resp["error"]
            raise BrokerRPCError(err["code"], err["message"])
        return resp["result"]

    # ── paramiko-compatible surface ────────────────────────────

    def ping(self) -> dict[str, Any]:
        return self._call("ping")

    def listdir_attr(self, path: str) -> list[_LikeSFTPAttributes]:
        r = self._call("listdir", {"path": path})
        return [
            _LikeSFTPAttributes(
                filename=e["name"], st_size=e["size"],
                st_mode=e["mode"], st_mtime=e["mtime"],
            )
            for e in r["entries"]
        ]

    def stat(self, path: str) -> _LikeSFTPAttributes:
        r = self._call("stat", {"path": path})
        e = r["entry"]
        return _LikeSFTPAttributes(
            filename=e["name"], st_size=e["size"],
            st_mode=e["mode"], st_mtime=e["mtime"],
        )

    def get(self, remote_path: str, local_path: str) -> dict[str, Any]:
        return self._call("get_full",
                           {"remote_path": remote_path,
                            "local_path": local_path})

    # ── Broker extensions ──────────────────────────────────────

    def glob_remote(self, pattern: str) -> list[str]:
        r = self._call("glob", {"pattern": pattern})
        return list(r["paths"])

    def dump_header(self, path: str) -> dict[str, Any]:
        return self._call("dump_header", {"path": path})

    def dump_metadata(self, path: str) -> dict[str, Any]:
        return self._call("dump_metadata", {"path": path})

    def exec_argv(self, argv: list[str],
                   timeout: float | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"argv": argv}
        if timeout is not None:
            params["timeout"] = timeout
        return self._call("exec", params)
