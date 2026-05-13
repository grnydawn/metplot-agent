"""The 9 JSON-RPC methods served by the broker.

Each method signature: f(holder, params, *, extra_allowed=None) -> dict.
On success returns a JSON-serializable result dict.
On error raises a BrokerError subclass; the server maps to JSON-RPC.

File-op methods (5) dispatch through holder.with_sftp(). Exec-backed
methods (3) dispatch through holder.exec_command() — that closes the
SFTP channel first, runs the command, leaves SFTP closed (next
with_sftp() reopens lazily). One-session-channel-at-a-time invariant
is enforced by the SessionHolder mutex.
"""
from __future__ import annotations

import base64
import fnmatch
import hashlib
import posixpath
import stat as statmod
from typing import Any, Callable

from src.ssh_broker.exec_policy import (
    BUILTIN_ALLOWLIST, is_allowed, quote_argv,
)
from src.ssh_broker.protocol import (
    CONNECTION_LOST, SFTP_ERROR, TOOL_NOT_FOUND, TOOL_NOT_IN_ALLOWLIST,
)


# ── BrokerError hierarchy ──────────────────────────────────────

class BrokerError(Exception):
    code: int = CONNECTION_LOST

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ConnectionLost(BrokerError):
    code = CONNECTION_LOST


class SFTPError(BrokerError):
    code = SFTP_ERROR


class ToolNotFoundError(BrokerError):
    code = TOOL_NOT_FOUND


class ToolNotInAllowlistError(BrokerError):
    code = TOOL_NOT_IN_ALLOWLIST


# ── Helpers ────────────────────────────────────────────────────

def _attr_to_dict(name: str, attr: Any) -> dict[str, Any]:
    mode = attr.st_mode or 0
    return {
        "name": name,
        "size": attr.st_size,
        "mode": mode,
        "mtime": attr.st_mtime,
        "is_dir": bool(statmod.S_ISDIR(mode)),
        "is_link": bool(statmod.S_ISLNK(mode)),
    }


def _wrap_oserrors(action: str, path: str, fn: Callable):
    try:
        return fn()
    except FileNotFoundError as e:
        raise SFTPError(f"not found: {path}") from e
    except OSError as e:
        raise SFTPError(f"{action}({path!r}): {e}") from e


# ── File-op methods ────────────────────────────────────────────

def listdir(holder, params: dict[str, Any], *,
             extra_allowed=None) -> dict[str, Any]:
    path = params["path"]

    def _do(sftp):
        return _wrap_oserrors("listdir", path,
                               lambda: sftp.listdir_attr(path))

    entries = holder.with_sftp(_do)
    return {"entries": [_attr_to_dict(a.filename, a) for a in entries]}


def stat(holder, params: dict[str, Any], *,
          extra_allowed=None) -> dict[str, Any]:
    path = params["path"]

    def _do(sftp):
        return _wrap_oserrors("stat", path, lambda: sftp.stat(path))

    a = holder.with_sftp(_do)
    return {"entry": _attr_to_dict(posixpath.basename(path), a)}


def glob(holder, params: dict[str, Any], *,
          extra_allowed=None) -> dict[str, Any]:
    pattern = params["pattern"]
    parent, basepat = posixpath.split(pattern)
    if not parent:
        parent = "."

    def _do(sftp):
        return _wrap_oserrors("listdir", parent,
                               lambda: sftp.listdir(parent))

    names = holder.with_sftp(_do)
    matches = sorted(
        posixpath.join(parent, n)
        for n in names if fnmatch.fnmatch(n, basepat)
    )
    return {"paths": matches}


def get_chunk(holder, params: dict[str, Any], *,
                extra_allowed=None) -> dict[str, Any]:
    path = params["path"]
    offset = int(params["offset"])
    length = int(params["length"])

    def _do(sftp):
        def _read():
            with sftp.open(path, "rb") as fh:
                fh.seek(offset)
                return fh.read(length)
        return _wrap_oserrors("get_chunk", path, _read)

    data = holder.with_sftp(_do)
    return {"data_b64": base64.b64encode(data).decode("ascii"),
            "size": len(data)}


def get_full(holder, params: dict[str, Any], *,
              extra_allowed=None) -> dict[str, Any]:
    remote = params["remote_path"]
    local = params["local_path"]

    def _do(sftp):
        return _wrap_oserrors("get_full", remote,
                               lambda: sftp.get(remote, local))

    holder.with_sftp(_do)
    h = hashlib.sha256()
    bytes_copied = 0
    with open(local, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
            bytes_copied += len(chunk)
    return {"bytes_copied": bytes_copied, "sha256": h.hexdigest()}


# ── Exec-backed methods ────────────────────────────────────────

def dump_header(holder, params: dict[str, Any], *,
                 extra_allowed=None) -> dict[str, Any]:
    path = params["path"]
    cmd = quote_argv(["ncdump", "-h", path])
    r = holder.exec_command(cmd, timeout=60.0)
    return {
        "cdl": r["stdout_bytes"].decode("utf-8", errors="replace"),
        "stderr": r["stderr_bytes"].decode("utf-8", errors="replace"),
        "exit_code": r["exit_code"],
    }


def dump_metadata(holder, params: dict[str, Any], *,
                   extra_allowed=None) -> dict[str, Any]:
    path = params["path"]
    cmd = quote_argv(["ncks", "-m", path])
    r = holder.exec_command(cmd, timeout=60.0)
    stderr_text = r["stderr_bytes"].decode("utf-8", errors="replace")
    if r["exit_code"] != 0 and (
        "command not found" in stderr_text
        or "No such file or directory" in stderr_text
    ):
        raise ToolNotFoundError(
            f"ncks unavailable on remote: {stderr_text.strip()}")
    return {
        "ncks_m": r["stdout_bytes"].decode("utf-8", errors="replace"),
        "stderr": stderr_text,
        "exit_code": r["exit_code"],
    }


def exec_(holder, params: dict[str, Any], *,
           extra_allowed=None) -> dict[str, Any]:
    argv = params["argv"]
    timeout = float(params.get("timeout", 60.0))
    if not argv:
        raise ToolNotInAllowlistError("(empty argv)")
    if not is_allowed(argv[0], extra_allowed=extra_allowed):
        raise ToolNotInAllowlistError(argv[0])
    cmd = quote_argv(argv)
    r = holder.exec_command(cmd, timeout=timeout)
    return {
        "stdout_b64": base64.b64encode(r["stdout_bytes"]).decode("ascii"),
        "stderr_b64": base64.b64encode(r["stderr_bytes"]).decode("ascii"),
        "exit_code": r["exit_code"],
    }


# ── Lifecycle ──────────────────────────────────────────────────

def ping(holder, params: dict[str, Any], *,
          extra_allowed=None) -> dict[str, Any]:
    extras = set(extra_allowed or [])
    return {
        "alive": True,
        "host": holder.host,
        "connected_at": holder.connected_at,
        "sftp_open": holder._sftp is not None,
        "allowed_exec_tools": sorted(BUILTIN_ALLOWLIST | extras),
    }


# ── Registry ───────────────────────────────────────────────────

METHODS: dict[str, Callable[..., dict[str, Any]]] = {
    "listdir": listdir,
    "stat": stat,
    "glob": glob,
    "get_chunk": get_chunk,
    "get_full": get_full,
    "dump_header": dump_header,
    "dump_metadata": dump_metadata,
    "exec": exec_,
    "ping": ping,
}
