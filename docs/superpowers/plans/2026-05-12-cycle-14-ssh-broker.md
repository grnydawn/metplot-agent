# Cycle-14 SSH Broker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **IMPORTANT — Spec drift note (2026-05-12, post-plan):** This plan
> was written before the cycle-14 spec was amended to add the
> SFTP↔exec channel state machine + read-only exec allowlist
> (commit `3dc4fd6`). Tasks 3, 4, 7, 12, 14, 19, 21, and 23 in this
> document are NOT fully aligned with the current spec. **The spec
> is the canonical contract** — see
> `docs/specs/2026-05-12-cycle-14-ssh-broker.md`. The orchestrator
> writes per-task subagent prompts grounded in the spec; the
> task-text in this plan is the starting template, not the final
> word. Specifically:
>
> - **Task 3** ships `SessionHolder` (not `SFTPHolder`) with a
>   single-session-channel mutex + state machine.
> - **Task 4** ships nine RPC methods (six file-op + three
>   exec-backed: `dump_header`, `dump_metadata`, `exec`).
> - **Task 4b (NEW)** ships `src/ssh_broker/exec_policy.py` with
>   the read-only `BUILTIN_ALLOWLIST` and `quote_argv()`.
> - **Task 7** adds `--allow-exec` to the CLI.
> - **Task 12** adds `dump_header` / `dump_metadata` / `exec_argv`
>   to `BrokerSFTPClient`.
> - **Task 14 (or new sub-task)** makes `inspect()` prefer
>   `broker.dump_header(path)` over `broker.get(...)` when broker
>   is present.
> - **Task 19 (skill)** and **Task 21 (architecture doc)** mention
>   the exec capability and allowlist.
> - **Task 23 (gate)** counts the additional methods/tests.

**Goal:** Ship a persistent `metplot-ssh-broker` daemon so the user authenticates **once in their own terminal before launching Claude Code**, and the metplot MCP reuses that authenticated SFTP channel without ever seeing the credential. Works on OLCF (`MaxSessions=1`).

**Architecture:** Small Python daemon holds one long-lived `paramiko.SFTPClient`. JSON-RPC 2.0 over a 0600 UNIX domain socket. MCP detects the socket and dispatches; falls back to direct paramiko when absent. All multiplexing happens at the SFTP protocol level inside one SSH channel (OLCF-compatible). Passcode is read by `getpass`, passed to `connect()` once, dropped immediately.

**Tech Stack:** Python 3.10+, paramiko (already a dep), stdlib `json` / `socket` / `selectors` / `getpass` / `argparse` / `subprocess`. No new third-party deps.

**Spec:** `docs/specs/2026-05-12-cycle-14-ssh-broker.md`

---

## File Structure

### NEW files

| Path | Responsibility |
|---|---|
| `src/ssh_broker/__init__.py` | Package marker. |
| `src/ssh_broker/protocol.py` | JSON-RPC 2.0 wire format: `make_request` / `make_response` / `make_error` / `encode` / `decode`. |
| `src/ssh_broker/methods.py` | The 6 JSON-RPC methods (`listdir`, `stat`, `glob`, `get_chunk`, `get_full`, `ping`) — each takes a `paramiko.SFTPClient` + params dict, returns a result dict. |
| `src/ssh_broker/sftp_holder.py` | `SFTPHolder` — owns the paramiko `SSHClient` + `SFTPClient`, keepalive thread, `is_alive()` check, clean shutdown. |
| `src/ssh_broker/server.py` | UNIX-socket server loop using `selectors`. Reads newline-delimited JSON, dispatches to methods, replies. Idle-timeout exit. |
| `src/ssh_broker/cli.py` | `main()` — argparse → `getpass.getpass()` → `paramiko.connect()` → drop passcode → call `server.serve_forever()`. Foreground, user backgrounds with `&` if desired. |
| `src/mcp/netcdf_reader/paths/ssh_broker.py` | `BrokerSFTPClient` — talks JSON-RPC over the local UNIX socket. Subset of `paramiko.SFTPClient` API the MCP uses. |
| `src/skills/netcdf-remote/SKILL.md` | Skill that guides users through broker setup when an `ssh://` path appears. |
| `docs/architecture/ssh-broker.md` | Design doc — protocol, lifecycle, threat model. |
| `tests/ssh_broker/__init__.py` + `tests/ssh_broker/unit/__init__.py` + `tests/ssh_broker/integration/__init__.py` | Test packages. |
| `tests/ssh_broker/conftest.py` | In-process paramiko sshd fixture. |
| `tests/ssh_broker/unit/test_protocol.py` | Round-trip protocol encoding. |
| `tests/ssh_broker/unit/test_methods.py` | The 6 methods against MagicMock SFTPClient. |
| `tests/ssh_broker/unit/test_sftp_holder.py` | Holder lifecycle with mock paramiko. |
| `tests/ssh_broker/unit/test_server.py` | Server loop with synthetic socket clients. |
| `tests/ssh_broker/unit/test_socket_permissions.py` | Socket created with mode 0600. |
| `tests/ssh_broker/unit/test_cli_args.py` | CLI argument parsing. |
| `tests/ssh_broker/integration/test_inproc_sshd.py` | End-to-end broker round-trip via in-process sshd. |
| `tests/ssh_broker/integration/test_idle_shutdown.py` | Broker exits within 5s of idle-timeout. |
| `tests/ssh_broker/integration/test_connection_lost.py` | Broker reports `connection_lost` after sshd dies. |
| `tests/mcp/netcdf_reader/unit/test_ssh_broker_client.py` | `BrokerSFTPClient` against a mock UNIX-socket server. |
| `tests/mcp/netcdf_reader/unit/test_ssh_classify_glob.py` | `ssh://host/path/*.nc` via mock broker. |
| `tests/mcp/netcdf_reader/integration/test_inspect_via_broker.py` | `inspect()` via broker + in-proc sshd. |

### MODIFIED files

| Path | Change |
|---|---|
| `src/mcp/netcdf_reader/paths/ssh.py` | Add `open_ssh_with_broker_fallback(path, ssh_config=None)`. |
| `src/mcp/netcdf_reader/paths/classify.py` | Add `PathKind.SSH_MULTI`. When `ssh://` URL contains glob chars, call broker; else current behavior. |
| `src/mcp/netcdf_reader/adapter.py` | Route ssh paths through `open_ssh_with_broker_fallback`. |
| `src/mcp/netcdf_reader/tools/inspect.py` | New `broker_required` error subcode wired alongside `ssh_auth_needed`. |
| `build/claude-code/metplot/mcp-servers/netcdf_reader/pyproject.toml` | Add `metplot-ssh-broker = "src.ssh_broker.cli:main"` under `[project.scripts]`. |
| `src/skills/netcdf-inspect/SKILL.md` | Add note about `broker_required` envelope and pointer to `netcdf-remote` skill. |
| `README.md` | New "Remote file access (OLCF and other OTP-protected hosts)" subsection. |
| `tests/targets/claude_code/test_mcp_smoke.py` | Verify `metplot-ssh-broker` entry-point is registered. |

---

## Conventions used in this plan

- Tests live next to existing tests (`tests/mcp/...`) or under the new `tests/ssh_broker/` for broker-only code.
- TDD: every task starts with a failing test, ends with a green test + commit.
- Commit messages: `cycle-14 task N: <one-line summary>` matches the cycle-13 style in `git log`.
- Run tests from repo root with `uv run pytest <path> -v`.
- Lint/type checks deferred to the final gate task — don't run them per-task.

---

## Task 1: Scaffold the broker package and test tree

**Files:**
- Create: `src/ssh_broker/__init__.py`
- Create: `tests/ssh_broker/__init__.py`
- Create: `tests/ssh_broker/unit/__init__.py`
- Create: `tests/ssh_broker/integration/__init__.py`
- Create: `tests/ssh_broker/unit/test_package_import.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/ssh_broker/unit/test_package_import.py
"""Cycle 14 smoke test: the new ssh_broker package imports cleanly."""
import importlib


def test_ssh_broker_package_imports():
    mod = importlib.import_module("src.ssh_broker")
    assert mod is not None
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/ssh_broker/unit/test_package_import.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'src.ssh_broker'`.

- [ ] **Step 3: Create the package + test-tree marker files**

```python
# src/ssh_broker/__init__.py
"""Persistent SSH/SFTP broker for OTP-protected remote hosts.

Started by the user in their own terminal BEFORE the AI target.
Holds one long-lived paramiko SFTPClient; serves JSON-RPC requests
over a 0600 UNIX socket. Credential never crosses the AI boundary.

See docs/architecture/ssh-broker.md.
"""
```

```python
# tests/ssh_broker/__init__.py
```

```python
# tests/ssh_broker/unit/__init__.py
```

```python
# tests/ssh_broker/integration/__init__.py
```

- [ ] **Step 4: Run test to verify it passes**

```
uv run pytest tests/ssh_broker/unit/test_package_import.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ssh_broker tests/ssh_broker
git commit -m "cycle-14 task 1: scaffold ssh_broker package and test tree"
```

---

## Task 2: JSON-RPC protocol primitives

**Files:**
- Create: `src/ssh_broker/protocol.py`
- Create: `tests/ssh_broker/unit/test_protocol.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/ssh_broker/unit/test_protocol.py
"""JSON-RPC 2.0 wire-format primitives."""
import json

import pytest

from src.ssh_broker.protocol import (
    JSONRPC_VERSION, INVALID_PARAMS, METHOD_NOT_FOUND, PARSE_ERROR,
    decode_line, encode_message, make_error, make_request, make_response,
)


def test_make_request_shape():
    r = make_request(req_id=7, method="listdir", params={"path": "/x"})
    assert r["jsonrpc"] == JSONRPC_VERSION
    assert r["id"] == 7
    assert r["method"] == "listdir"
    assert r["params"] == {"path": "/x"}


def test_make_request_defaults_params_to_empty_dict():
    r = make_request(req_id=1, method="ping")
    assert r["params"] == {}


def test_make_response_shape():
    r = make_response(req_id=3, result={"ok": True})
    assert r["jsonrpc"] == JSONRPC_VERSION
    assert r["id"] == 3
    assert r["result"] == {"ok": True}
    assert "error" not in r


def test_make_error_shape():
    r = make_error(req_id=4, code=METHOD_NOT_FOUND, message="unknown method 'foo'")
    assert r["jsonrpc"] == JSONRPC_VERSION
    assert r["id"] == 4
    assert r["error"] == {"code": METHOD_NOT_FOUND, "message": "unknown method 'foo'"}
    assert "result" not in r


def test_encode_appends_newline_and_utf8():
    line = encode_message(make_request(1, "ping"))
    assert isinstance(line, bytes)
    assert line.endswith(b"\n")
    # Round-trip via json
    obj = json.loads(line.decode("utf-8"))
    assert obj["method"] == "ping"


def test_encode_uses_compact_separators():
    # No whitespace between key:value or , — keeps wire small.
    line = encode_message({"a": 1, "b": [2, 3]})
    assert b" " not in line


def test_decode_parses_valid_json():
    obj = decode_line(b'{"a":1}\n')
    assert obj == {"a": 1}


def test_decode_strips_trailing_newline():
    obj = decode_line(b'{"a":1}')
    assert obj == {"a": 1}


def test_decode_raises_on_malformed():
    with pytest.raises(json.JSONDecodeError):
        decode_line(b'not json')


def test_constants_are_standard_jsonrpc_codes():
    # Spec: https://www.jsonrpc.org/specification#error_object
    assert PARSE_ERROR == -32700
    assert INVALID_PARAMS == -32602
    assert METHOD_NOT_FOUND == -32601
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/ssh_broker/unit/test_protocol.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ssh_broker.protocol'`.

- [ ] **Step 3: Implement protocol primitives**

```python
# src/ssh_broker/protocol.py
"""JSON-RPC 2.0 wire format for the metplot-ssh-broker.

Wire form: newline-delimited JSON over a UNIX domain socket.
Each line is one JSON object.

Request:   {"jsonrpc":"2.0","id":N,"method":"...","params":{...}}
Response:  {"jsonrpc":"2.0","id":N,"result":{...}}
Error:     {"jsonrpc":"2.0","id":N,"error":{"code":int,"message":str}}
"""
from __future__ import annotations

import json
from typing import Any, TypedDict

JSONRPC_VERSION = "2.0"

# Standard JSON-RPC 2.0 error codes (https://www.jsonrpc.org/specification)
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# Broker-specific error codes (-32000..-32099 is the "Server error" range)
CONNECTION_LOST = -32000
SFTP_ERROR = -32001


class Request(TypedDict):
    jsonrpc: str
    id: int
    method: str
    params: dict[str, Any]


class ErrorPayload(TypedDict):
    code: int
    message: str


class Response(TypedDict, total=False):
    jsonrpc: str
    id: int
    result: dict[str, Any]
    error: ErrorPayload


def make_request(req_id: int, method: str,
                  params: dict[str, Any] | None = None) -> Request:
    return {"jsonrpc": JSONRPC_VERSION, "id": req_id, "method": method,
            "params": params or {}}


def make_response(req_id: int, result: dict[str, Any]) -> Response:
    return {"jsonrpc": JSONRPC_VERSION, "id": req_id, "result": result}


def make_error(req_id: int, code: int, message: str) -> Response:
    return {"jsonrpc": JSONRPC_VERSION, "id": req_id,
            "error": {"code": code, "message": message}}


def encode_message(msg: dict[str, Any]) -> bytes:
    """Serialize to a single newline-terminated UTF-8 line."""
    return (json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8")


def decode_line(line: bytes) -> dict[str, Any]:
    """Deserialize one newline-terminated line (newline optional)."""
    return json.loads(line.decode("utf-8").rstrip("\n"))
```

- [ ] **Step 4: Run test to verify it passes**

```
uv run pytest tests/ssh_broker/unit/test_protocol.py -v
```
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ssh_broker/protocol.py tests/ssh_broker/unit/test_protocol.py
git commit -m "cycle-14 task 2: JSON-RPC 2.0 protocol primitives"
```

---

## Task 3: SFTPHolder lifecycle

**Files:**
- Create: `src/ssh_broker/sftp_holder.py`
- Create: `tests/ssh_broker/unit/test_sftp_holder.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/ssh_broker/unit/test_sftp_holder.py
"""SFTPHolder owns the paramiko SSHClient + SFTPClient lifecycle.

Hard invariant: ONE SFTP channel per holder. Never opens a second
session channel. Compatible with OLCF MaxSessions=1.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.ssh_broker.sftp_holder import SFTPHolder


def _mk_holder(client_mock):
    transport = MagicMock()
    transport.is_active.return_value = True
    client_mock.get_transport.return_value = transport
    sftp = MagicMock()
    client_mock.open_sftp.return_value = sftp
    return SFTPHolder(client=client_mock, host="h", user="u")


def test_holder_opens_one_sftp_channel():
    cli = MagicMock()
    h = _mk_holder(cli)
    assert h.sftp is cli.open_sftp.return_value
    cli.open_sftp.assert_called_once()


def test_holder_sets_keepalive_on_transport():
    cli = MagicMock()
    h = _mk_holder(cli)
    h.transport.set_keepalive.assert_called_with(30)


def test_holder_is_alive_true_when_transport_active():
    cli = MagicMock()
    h = _mk_holder(cli)
    assert h.is_alive() is True


def test_holder_is_alive_false_when_transport_inactive():
    cli = MagicMock()
    h = _mk_holder(cli)
    h.transport.is_active.return_value = False
    assert h.is_alive() is False


def test_holder_close_closes_sftp_then_client():
    cli = MagicMock()
    h = _mk_holder(cli)
    h.close()
    h.sftp.close.assert_called_once()
    cli.close.assert_called_once()


def test_holder_close_swallows_sftp_errors():
    """Shutdown must be best-effort — paramiko sometimes raises on
    close after the transport is already gone."""
    cli = MagicMock()
    h = _mk_holder(cli)
    h.sftp.close.side_effect = OSError("already closed")
    h.close()  # must not raise
    cli.close.assert_called_once()


def test_holder_metadata_recorded():
    cli = MagicMock()
    h = _mk_holder(cli)
    assert h.host == "h"
    assert h.user == "u"
    assert h.connected_at is not None  # ISO datetime string
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/ssh_broker/unit/test_sftp_holder.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ssh_broker.sftp_holder'`.

- [ ] **Step 3: Implement SFTPHolder**

```python
# src/ssh_broker/sftp_holder.py
"""Holds one paramiko SSHClient + one SFTPClient.

Hard invariant: ONE SFTP channel per holder. The broker NEVER opens
a second session channel for this connection — that would fail on
OLCF where the sshd enforces MaxSessions=1.

Construction takes an already-connected client. CLI auth happens
elsewhere and the credential is dropped before the holder ever sees
the client.
"""
from __future__ import annotations

import datetime as _dt
from typing import Any

# paramiko types kept loose — `Any` lets us swap mocks in tests.


class SFTPHolder:
    def __init__(self, *, client: Any, host: str, user: str,
                  keepalive_interval: int = 30) -> None:
        self.client = client
        self.host = host
        self.user = user
        self.transport = client.get_transport()
        if self.transport is not None:
            self.transport.set_keepalive(keepalive_interval)
        # ONE channel — opened here, reused for every method call.
        self.sftp = client.open_sftp()
        self.connected_at = _dt.datetime.now(_dt.timezone.utc).isoformat()

    def is_alive(self) -> bool:
        return bool(self.transport and self.transport.is_active())

    def close(self) -> None:
        # Best-effort. SFTPClient.close() can raise OSError if the
        # transport is already gone — swallow so SSHClient.close()
        # still runs.
        try:
            self.sftp.close()
        except Exception:
            pass
        try:
            self.client.close()
        except Exception:
            pass
```

- [ ] **Step 4: Run test to verify it passes**

```
uv run pytest tests/ssh_broker/unit/test_sftp_holder.py -v
```
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ssh_broker/sftp_holder.py tests/ssh_broker/unit/test_sftp_holder.py
git commit -m "cycle-14 task 3: SFTPHolder lifecycle with single-channel invariant"
```

---

## Task 4: The 6 JSON-RPC methods

**Files:**
- Create: `src/ssh_broker/methods.py`
- Create: `tests/ssh_broker/unit/test_methods.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/ssh_broker/unit/test_methods.py
"""The 6 broker JSON-RPC methods.

Each takes an SFTPClient + JSON params and returns a result dict.
Errors raise BrokerError subclasses; the server layer maps them to
JSON-RPC error responses.
"""
from __future__ import annotations

import base64
import os
import stat as statmod
from unittest.mock import MagicMock

import pytest

from src.ssh_broker.methods import (
    METHODS, BrokerError, ConnectionLost, SFTPError,
    get_chunk, get_full, glob, listdir, ping, stat,
)


def _attr(name: str, size: int = 100, mode: int = 0o100644, mtime: float = 1.0):
    a = MagicMock()
    a.filename = name
    a.st_size = size
    a.st_mode = mode
    a.st_mtime = mtime
    return a


def test_registry_has_six_methods():
    assert set(METHODS) == {"listdir", "stat", "glob", "get_chunk",
                             "get_full", "ping"}


def test_ping_returns_alive():
    sftp = MagicMock()
    r = ping(sftp, {})
    assert r == {"alive": True}


def test_listdir_returns_entries():
    sftp = MagicMock()
    sftp.listdir_attr.return_value = [
        _attr("a.nc", size=42), _attr("b.nc", size=99),
    ]
    r = listdir(sftp, {"path": "/data"})
    sftp.listdir_attr.assert_called_with("/data")
    assert len(r["entries"]) == 2
    assert r["entries"][0]["name"] == "a.nc"
    assert r["entries"][0]["size"] == 42
    assert r["entries"][0]["is_dir"] is False


def test_listdir_marks_directories():
    sftp = MagicMock()
    sftp.listdir_attr.return_value = [
        _attr("sub", mode=statmod.S_IFDIR | 0o755),
    ]
    r = listdir(sftp, {"path": "/d"})
    assert r["entries"][0]["is_dir"] is True


def test_listdir_raises_sftp_error_on_not_found():
    sftp = MagicMock()
    sftp.listdir_attr.side_effect = FileNotFoundError("nope")
    with pytest.raises(SFTPError):
        listdir(sftp, {"path": "/missing"})


def test_stat_returns_entry():
    sftp = MagicMock()
    sftp.stat.return_value = _attr("ignored", size=7)
    r = stat(sftp, {"path": "/x.nc"})
    sftp.stat.assert_called_with("/x.nc")
    assert r["entry"]["name"] == "x.nc"  # derived from basename
    assert r["entry"]["size"] == 7


def test_glob_matches_pattern_against_listdir():
    sftp = MagicMock()
    sftp.listdir.return_value = ["a.nc", "b.nc", "skip.txt", "c.nc"]
    r = glob(sftp, {"pattern": "/data/*.nc"})
    sftp.listdir.assert_called_with("/data")
    assert r["paths"] == ["/data/a.nc", "/data/b.nc", "/data/c.nc"]


def test_glob_handles_relative_pattern():
    sftp = MagicMock()
    sftp.listdir.return_value = ["x.nc"]
    r = glob(sftp, {"pattern": "*.nc"})
    sftp.listdir.assert_called_with(".")
    assert r["paths"] == ["./x.nc"]


def test_glob_empty_when_no_matches():
    sftp = MagicMock()
    sftp.listdir.return_value = ["a.txt", "b.log"]
    r = glob(sftp, {"pattern": "/d/*.nc"})
    assert r["paths"] == []


def test_get_chunk_reads_offset_and_length():
    sftp = MagicMock()
    fh = MagicMock()
    fh.read.return_value = b"hello"
    sftp.open.return_value.__enter__.return_value = fh
    r = get_chunk(sftp, {"path": "/x.nc", "offset": 4, "length": 5})
    fh.seek.assert_called_with(4)
    fh.read.assert_called_with(5)
    assert base64.b64decode(r["data_b64"]) == b"hello"
    assert r["size"] == 5


def test_get_full_writes_local_file_and_returns_sha256(tmp_path):
    remote = "/remote/file.nc"
    local = str(tmp_path / "out.nc")
    sftp = MagicMock()
    # Simulate sftp.get by writing bytes to the local path.
    def fake_get(r, l):
        with open(l, "wb") as fh:
            fh.write(b"abc" * 10)
    sftp.get.side_effect = fake_get
    r = get_full(sftp, {"remote_path": remote, "local_path": local})
    sftp.get.assert_called_with(remote, local)
    assert r["bytes_copied"] == 30
    # sha256("abc"*10).hexdigest()
    import hashlib
    assert r["sha256"] == hashlib.sha256(b"abc" * 10).hexdigest()


def test_brokererror_carries_jsonrpc_code():
    assert ConnectionLost("x").code == -32000
    assert SFTPError("x").code == -32001
    # Base class default
    assert BrokerError("x").code == -32000
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/ssh_broker/unit/test_methods.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ssh_broker.methods'`.

- [ ] **Step 3: Implement the methods**

```python
# src/ssh_broker/methods.py
"""The 6 JSON-RPC methods served by the broker.

Each method:
  signature: f(sftp: paramiko.SFTPClient, params: dict) -> dict
  on success: returns a JSON-serializable result dict
  on error:   raises BrokerError (mapped to JSON-RPC error response)

All file operations multiplex through ONE long-lived SFTPClient — no
exec channels, no second SFTP channels. OLCF-compatible.
"""
from __future__ import annotations

import base64
import fnmatch
import hashlib
import posixpath
import stat as statmod
from typing import Any, Callable

from src.ssh_broker.protocol import CONNECTION_LOST, SFTP_ERROR


class BrokerError(Exception):
    code: int = CONNECTION_LOST

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ConnectionLost(BrokerError):
    code = CONNECTION_LOST


class SFTPError(BrokerError):
    code = SFTP_ERROR


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


def listdir(sftp: Any, params: dict[str, Any]) -> dict[str, Any]:
    path = params["path"]
    try:
        entries = sftp.listdir_attr(path)
    except FileNotFoundError as e:
        raise SFTPError(f"not found: {path}") from e
    except OSError as e:
        raise SFTPError(f"listdir({path!r}): {e}") from e
    return {"entries": [_attr_to_dict(a.filename, a) for a in entries]}


def stat(sftp: Any, params: dict[str, Any]) -> dict[str, Any]:
    path = params["path"]
    try:
        a = sftp.stat(path)
    except FileNotFoundError as e:
        raise SFTPError(f"not found: {path}") from e
    except OSError as e:
        raise SFTPError(f"stat({path!r}): {e}") from e
    return {"entry": _attr_to_dict(posixpath.basename(path), a)}


def glob(sftp: Any, params: dict[str, Any]) -> dict[str, Any]:
    pattern = params["pattern"]
    parent, basepat = posixpath.split(pattern)
    if not parent:
        parent = "."
    try:
        names = sftp.listdir(parent)
    except FileNotFoundError as e:
        raise SFTPError(f"parent not found: {parent}") from e
    except OSError as e:
        raise SFTPError(f"listdir({parent!r}): {e}") from e
    matches = sorted(
        posixpath.join(parent, n)
        for n in names if fnmatch.fnmatch(n, basepat)
    )
    return {"paths": matches}


def get_chunk(sftp: Any, params: dict[str, Any]) -> dict[str, Any]:
    path = params["path"]
    offset = int(params["offset"])
    length = int(params["length"])
    try:
        with sftp.open(path, "rb") as fh:
            fh.seek(offset)
            data = fh.read(length)
    except FileNotFoundError as e:
        raise SFTPError(f"not found: {path}") from e
    except OSError as e:
        raise SFTPError(f"get_chunk({path!r}): {e}") from e
    return {"data_b64": base64.b64encode(data).decode("ascii"),
            "size": len(data)}


def get_full(sftp: Any, params: dict[str, Any]) -> dict[str, Any]:
    remote = params["remote_path"]
    local = params["local_path"]
    try:
        sftp.get(remote, local)
    except FileNotFoundError as e:
        raise SFTPError(f"not found: {remote}") from e
    except OSError as e:
        raise SFTPError(f"get_full({remote!r}): {e}") from e
    # Hash from the local file we just wrote.
    h = hashlib.sha256()
    bytes_copied = 0
    with open(local, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
            bytes_copied += len(chunk)
    return {"bytes_copied": bytes_copied, "sha256": h.hexdigest()}


def ping(sftp: Any, params: dict[str, Any]) -> dict[str, Any]:
    return {"alive": True}


METHODS: dict[str, Callable[[Any, dict[str, Any]], dict[str, Any]]] = {
    "listdir": listdir,
    "stat": stat,
    "glob": glob,
    "get_chunk": get_chunk,
    "get_full": get_full,
    "ping": ping,
}
```

- [ ] **Step 4: Run test to verify it passes**

```
uv run pytest tests/ssh_broker/unit/test_methods.py -v
```
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ssh_broker/methods.py tests/ssh_broker/unit/test_methods.py
git commit -m "cycle-14 task 4: 6 JSON-RPC methods (listdir/stat/glob/get_chunk/get_full/ping)"
```

---

## Task 5: UNIX-socket server loop

**Files:**
- Create: `src/ssh_broker/server.py`
- Create: `tests/ssh_broker/unit/test_server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/ssh_broker/unit/test_server.py
"""UNIX-socket server: dispatch JSON-RPC requests over a 0600 socket.

Tests spin up the server in a background thread, connect a synthetic
client (stdlib socket), send requests, read replies. No paramiko —
the SFTPHolder is mocked.
"""
from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.ssh_broker.server import serve_forever, BrokerSession


def _round_trip(sock_path: str, request: dict) -> dict:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.connect(sock_path)
        s.sendall((json.dumps(request) + "\n").encode("utf-8"))
        # Read until newline.
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
    # Wait for socket to appear.
    deadline = time.time() + 5
    while not Path(sock_path).exists():
        if time.time() > deadline:
            raise TimeoutError("server didn't start")
        time.sleep(0.05)
    return sock_path, stop, t


def test_server_dispatches_ping(tmp_path):
    holder = MagicMock()
    holder.is_alive.return_value = True
    sock_path, stop, t = _start_server(tmp_path, holder)
    try:
        resp = _round_trip(sock_path, {"jsonrpc": "2.0", "id": 1,
                                         "method": "ping", "params": {}})
        assert resp["id"] == 1
        assert resp["result"] == {"alive": True}
    finally:
        stop.set()
        t.join(timeout=5)


def test_server_returns_method_not_found(tmp_path):
    holder = MagicMock()
    holder.is_alive.return_value = True
    sock_path, stop, t = _start_server(tmp_path, holder)
    try:
        resp = _round_trip(sock_path, {"jsonrpc": "2.0", "id": 2,
                                         "method": "not_a_method"})
        assert resp["id"] == 2
        assert resp["error"]["code"] == -32601
    finally:
        stop.set()
        t.join(timeout=5)


def test_server_dispatches_listdir_through_holder(tmp_path):
    holder = MagicMock()
    holder.is_alive.return_value = True
    fake_attr = MagicMock(); fake_attr.filename = "x.nc"
    fake_attr.st_size = 1; fake_attr.st_mode = 0o100644; fake_attr.st_mtime = 0
    holder.sftp.listdir_attr.return_value = [fake_attr]
    sock_path, stop, t = _start_server(tmp_path, holder)
    try:
        resp = _round_trip(sock_path, {"jsonrpc": "2.0", "id": 3,
                                         "method": "listdir",
                                         "params": {"path": "/d"}})
        assert resp["result"]["entries"][0]["name"] == "x.nc"
    finally:
        stop.set()
        t.join(timeout=5)


def test_server_reports_connection_lost_when_holder_dead(tmp_path):
    holder = MagicMock()
    holder.is_alive.return_value = False
    sock_path, stop, t = _start_server(tmp_path, holder)
    try:
        resp = _round_trip(sock_path, {"jsonrpc": "2.0", "id": 4,
                                         "method": "ping"})
        assert resp["error"]["code"] == -32000  # CONNECTION_LOST
    finally:
        stop.set()
        t.join(timeout=5)


def test_server_creates_socket_with_0600(tmp_path):
    holder = MagicMock()
    holder.is_alive.return_value = True
    sock_path, stop, t = _start_server(tmp_path, holder)
    try:
        mode = Path(sock_path).stat().st_mode & 0o777
        assert mode == 0o600
    finally:
        stop.set()
        t.join(timeout=5)


def test_server_removes_socket_on_shutdown(tmp_path):
    holder = MagicMock()
    holder.is_alive.return_value = True
    sock_path, stop, t = _start_server(tmp_path, holder)
    assert Path(sock_path).exists()
    stop.set()
    t.join(timeout=5)
    assert not Path(sock_path).exists()
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/ssh_broker/unit/test_server.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ssh_broker.server'`.

- [ ] **Step 3: Implement the server loop**

```python
# src/ssh_broker/server.py
"""UNIX-socket server loop for the metplot-ssh-broker.

Single-threaded `selectors` loop. Reads newline-delimited JSON-RPC
requests, dispatches to METHODS, writes the response. SFTP operations
serialize through the one SFTPHolder — OLCF can't parallelize them
anyway since there's only one SFTP channel.
"""
from __future__ import annotations

import os
import selectors
import socket
import threading
import time
from pathlib import Path
from typing import Any

from src.ssh_broker.methods import METHODS, BrokerError, ConnectionLost
from src.ssh_broker.protocol import (
    CONNECTION_LOST, INTERNAL_ERROR, INVALID_PARAMS, METHOD_NOT_FOUND,
    PARSE_ERROR, decode_line, encode_message, make_error, make_response,
)


class BrokerSession:
    """Per-client read buffer and reply queue."""
    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.read_buf = bytearray()
        self.write_buf = bytearray()


def _dispatch_one(holder: Any, line: bytes) -> bytes:
    """Parse one line, dispatch, return one encoded reply."""
    try:
        req = decode_line(line)
    except Exception:
        return encode_message(make_error(0, PARSE_ERROR, "parse error"))
    req_id = req.get("id", 0)
    method = req.get("method", "")
    params = req.get("params") or {}

    if not holder.is_alive():
        return encode_message(make_error(req_id, CONNECTION_LOST,
                                          "connection lost"))

    fn = METHODS.get(method)
    if fn is None:
        return encode_message(make_error(req_id, METHOD_NOT_FOUND,
                                          f"unknown method {method!r}"))
    try:
        result = fn(holder.sftp, params)
    except KeyError as e:
        return encode_message(make_error(req_id, INVALID_PARAMS,
                                          f"missing param: {e.args[0]!r}"))
    except BrokerError as e:
        return encode_message(make_error(req_id, e.code, e.message))
    except Exception as e:
        return encode_message(make_error(req_id, INTERNAL_ERROR,
                                          f"{type(e).__name__}: {e}"))
    return encode_message(make_response(req_id, result))


def serve_forever(
    *, holder: Any, socket_path: str,
    stop_event: threading.Event | None = None,
    idle_timeout: float | None = None,
    poll_interval: float = 0.2,
) -> None:
    """Block until stop_event is set or idle_timeout elapses.

    holder: an SFTPHolder (or mock with `is_alive()` + `sftp`).
    socket_path: where to bind the UNIX domain socket.
    """
    stop = stop_event or threading.Event()
    p = Path(socket_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        p.unlink()

    server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server_sock.setblocking(False)
    server_sock.bind(socket_path)
    os.chmod(socket_path, 0o600)
    server_sock.listen(8)

    sel = selectors.DefaultSelector()
    sel.register(server_sock, selectors.EVENT_READ, data=None)
    sessions: dict[int, BrokerSession] = {}

    last_activity = time.time()

    try:
        while not stop.is_set():
            events = sel.select(timeout=poll_interval)
            for key, mask in events:
                if key.data is None:
                    # Accept
                    conn, _ = server_sock.accept()
                    conn.setblocking(False)
                    sess = BrokerSession(conn)
                    sessions[conn.fileno()] = sess
                    sel.register(conn, selectors.EVENT_READ
                                 | selectors.EVENT_WRITE, data=sess)
                else:
                    sess: BrokerSession = key.data
                    if mask & selectors.EVENT_READ:
                        try:
                            chunk = sess.sock.recv(4096)
                        except (BlockingIOError, InterruptedError):
                            continue
                        if not chunk:
                            sel.unregister(sess.sock)
                            sess.sock.close()
                            sessions.pop(sess.sock.fileno(), None)
                            continue
                        sess.read_buf.extend(chunk)
                        last_activity = time.time()
                        # Split on newline; dispatch each complete line.
                        while b"\n" in sess.read_buf:
                            nl = sess.read_buf.index(b"\n")
                            line = bytes(sess.read_buf[:nl + 1])
                            del sess.read_buf[:nl + 1]
                            reply = _dispatch_one(holder, line)
                            sess.write_buf.extend(reply)
                    if mask & selectors.EVENT_WRITE and sess.write_buf:
                        try:
                            n = sess.sock.send(sess.write_buf)
                        except (BlockingIOError, InterruptedError):
                            continue
                        del sess.write_buf[:n]
            # Idle-timeout check
            if idle_timeout is not None:
                if time.time() - last_activity > idle_timeout:
                    break
    finally:
        for sess in list(sessions.values()):
            try:
                sel.unregister(sess.sock)
                sess.sock.close()
            except Exception:
                pass
        try:
            sel.unregister(server_sock)
        except Exception:
            pass
        server_sock.close()
        try:
            Path(socket_path).unlink()
        except FileNotFoundError:
            pass
```

- [ ] **Step 4: Run test to verify it passes**

```
uv run pytest tests/ssh_broker/unit/test_server.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ssh_broker/server.py tests/ssh_broker/unit/test_server.py
git commit -m "cycle-14 task 5: UNIX-socket server loop with selectors dispatch"
```

---

## Task 6: Socket-permission unit test (separate file, kept focused)

**Files:**
- Create: `tests/ssh_broker/unit/test_socket_permissions.py`

- [ ] **Step 1: Write the failing test (will turn out to pass given Task 5 — but keep it for explicit security regression coverage)**

```python
# tests/ssh_broker/unit/test_socket_permissions.py
"""The broker socket must be 0600 — credential-equivalent surface."""
from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

from src.ssh_broker.server import serve_forever


def test_socket_mode_is_0600(tmp_path):
    holder = MagicMock()
    holder.is_alive.return_value = True
    sock_path = str(tmp_path / "b.sock")
    stop = threading.Event()
    t = threading.Thread(target=serve_forever,
                          kwargs=dict(holder=holder, socket_path=sock_path,
                                      stop_event=stop), daemon=True)
    t.start()
    deadline = time.time() + 3
    while not Path(sock_path).exists():
        if time.time() > deadline:
            raise TimeoutError
        time.sleep(0.05)
    try:
        st = Path(sock_path).stat()
        assert (st.st_mode & 0o777) == 0o600, (
            f"expected 0600, got {oct(st.st_mode & 0o777)}")
    finally:
        stop.set()
        t.join(timeout=5)


def test_socket_parent_dir_created(tmp_path):
    holder = MagicMock()
    holder.is_alive.return_value = True
    nested = tmp_path / "a" / "b" / "c" / "broker.sock"
    stop = threading.Event()
    t = threading.Thread(target=serve_forever,
                          kwargs=dict(holder=holder, socket_path=str(nested),
                                      stop_event=stop), daemon=True)
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
```

- [ ] **Step 2: Run test to verify it passes (no new implementation needed)**

```
uv run pytest tests/ssh_broker/unit/test_socket_permissions.py -v
```
Expected: 2 passed (Task 5's server already enforces these).

- [ ] **Step 3: Commit**

```bash
git add tests/ssh_broker/unit/test_socket_permissions.py
git commit -m "cycle-14 task 6: explicit 0600 socket-permission regression tests"
```

---

## Task 7: CLI entry point with argparse + getpass

**Files:**
- Create: `src/ssh_broker/cli.py`
- Create: `tests/ssh_broker/unit/test_cli_args.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/ssh_broker/unit/test_cli_args.py
"""CLI parses args correctly and the parser is reachable for inspection."""
from __future__ import annotations

import pytest

from src.ssh_broker.cli import build_parser, default_socket_path


def test_parser_accepts_host_positional():
    p = build_parser()
    ns = p.parse_args(["home.ccs.ornl.gov"])
    assert ns.host == "home.ccs.ornl.gov"
    assert ns.port == 22
    assert ns.user is None
    assert ns.idle_timeout == 7200.0
    assert ns.keepalive == 30


def test_parser_accepts_user_and_port():
    p = build_parser()
    ns = p.parse_args(["--user", "alice", "--port", "2222", "x.example"])
    assert ns.user == "alice"
    assert ns.port == 2222
    assert ns.host == "x.example"


def test_parser_accepts_socket_dir():
    p = build_parser()
    ns = p.parse_args(["--socket-dir", "/tmp/foo", "h"])
    assert ns.socket_dir == "/tmp/foo"


def test_default_socket_path_uses_xdg_runtime_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    p = default_socket_path("home.ccs.ornl.gov", socket_dir=None)
    assert p == str(tmp_path / "metplot-ssh" / "home.ccs.ornl.gov.sock")


def test_default_socket_path_falls_back_to_tmp(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    p = default_socket_path("h.example", socket_dir=None)
    assert p == "/tmp/metplot-ssh/h.example.sock"


def test_default_socket_path_honors_explicit_dir():
    p = default_socket_path("h", socket_dir="/my/dir")
    assert p == "/my/dir/h.sock"


def test_parser_help_does_not_crash():
    p = build_parser()
    with pytest.raises(SystemExit):
        p.parse_args(["--help"])
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/ssh_broker/unit/test_cli_args.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ssh_broker.cli'`.

- [ ] **Step 3: Implement the CLI**

```python
# src/ssh_broker/cli.py
"""metplot-ssh-broker CLI.

User invokes this in their own terminal BEFORE launching Claude Code:

    metplot-ssh-broker home.ccs.ornl.gov

The CLI prompts via getpass (passcode visible only to the user's
terminal), passes it to paramiko.connect(), drops it from memory,
then runs the JSON-RPC server. Foreground process — the user can
background it with `&` or run it in a separate tmux pane.
"""
from __future__ import annotations

import argparse
import getpass
import os
import signal
import sys
import threading
from pathlib import Path
from typing import Any

import paramiko

from src.ssh_broker.server import serve_forever
from src.ssh_broker.sftp_holder import SFTPHolder


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="metplot-ssh-broker",
        description=(
            "Persistent SSH/SFTP broker. Authenticates once in your "
            "terminal, exposes a local UNIX socket the metplot MCP "
            "uses without ever seeing your credential."
        ),
    )
    p.add_argument("host", help="remote hostname (e.g. home.ccs.ornl.gov)")
    p.add_argument("--user", default=None,
                    help="remote username (default: from ~/.ssh/config or $USER)")
    p.add_argument("--port", type=int, default=22, help="SSH port (default 22)")
    p.add_argument("--socket-dir", default=None,
                    help="directory for the UNIX socket "
                          "(default: $XDG_RUNTIME_DIR/metplot-ssh or /tmp/metplot-ssh)")
    p.add_argument("--idle-timeout", type=float, default=7200.0,
                    help="exit after N seconds with no requests (default 7200)")
    p.add_argument("--keepalive", type=int, default=30,
                    help="paramiko keepalive interval in seconds (default 30)")
    return p


def default_socket_path(host: str, socket_dir: str | None) -> str:
    if socket_dir is not None:
        base = socket_dir
    else:
        runtime = os.environ.get("XDG_RUNTIME_DIR")
        base = os.path.join(runtime, "metplot-ssh") if runtime \
            else "/tmp/metplot-ssh"
    return str(Path(base) / f"{host}.sock")


def _authenticate(host: str, user: str, port: int,
                   keepalive: int) -> SFTPHolder:
    """Read passcode interactively; connect; drop credential immediately."""
    # getpass writes the prompt to /dev/tty when available — never echoes.
    passcode = getpass.getpass(
        f"{user}@{host}:{port} passcode (in-memory only, will be dropped): "
    )
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host, port=port, username=user,
            password=passcode,
            allow_agent=False, look_for_keys=False, timeout=15,
        )
    finally:
        # Best-effort scrub. The Python str is immutable so we can't
        # zero the buffer; relying on the local binding falling out of
        # scope at function return.
        passcode = ""
        del passcode
    return SFTPHolder(client=client, host=host, user=user,
                       keepalive_interval=keepalive)


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    user = ns.user or os.environ.get("USER") or "root"
    sock_path = default_socket_path(ns.host, ns.socket_dir)

    if Path(sock_path).exists():
        print(f"ERROR: {sock_path} already exists. Another broker may be "
              f"running for this host.", file=sys.stderr)
        return 3

    print(f"Connecting to {user}@{ns.host}:{ns.port}...", file=sys.stderr)
    try:
        holder = _authenticate(ns.host, user, ns.port, ns.keepalive)
    except paramiko.AuthenticationException:
        print("ERROR: authentication failed.", file=sys.stderr)
        return 4
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 5

    print(f"Connected. Socket: {sock_path}", file=sys.stderr)
    print(f"Leave this process running. Press Ctrl-C to exit.",
          file=sys.stderr)

    stop = threading.Event()
    def _on_signal(signum: int, _frame: Any) -> None:
        print(f"Received signal {signum}, shutting down.", file=sys.stderr)
        stop.set()
    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    try:
        serve_forever(holder=holder, socket_path=sock_path,
                       stop_event=stop, idle_timeout=ns.idle_timeout)
    finally:
        holder.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

```
uv run pytest tests/ssh_broker/unit/test_cli_args.py -v
```
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ssh_broker/cli.py tests/ssh_broker/unit/test_cli_args.py
git commit -m "cycle-14 task 7: CLI entry point with getpass + credential drop"
```

---

## Task 8: In-process paramiko sshd fixture

**Files:**
- Create: `tests/ssh_broker/conftest.py`
- Create: `tests/ssh_broker/integration/test_inproc_sshd_fixture_smoke.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/ssh_broker/integration/test_inproc_sshd_fixture_smoke.py
"""Smoke test for the inproc_sshd fixture itself.

If this passes, all later integration tests can rely on the fixture.
"""
from __future__ import annotations

import paramiko


def test_inproc_sshd_accepts_password_auth(inproc_sshd):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname="127.0.0.1", port=inproc_sshd.port,
                    username="testuser", password="testpass",
                    allow_agent=False, look_for_keys=False)
    sftp = client.open_sftp()
    # The fixture seeds a root with one .nc file.
    names = sftp.listdir(inproc_sshd.root)
    assert "alpha.nc" in names
    sftp.close()
    client.close()
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/ssh_broker/integration/test_inproc_sshd_fixture_smoke.py -v
```
Expected: FAIL — fixture `inproc_sshd` not found.

- [ ] **Step 3: Implement the fixture**

```python
# tests/ssh_broker/conftest.py
"""In-process paramiko sshd for integration testing.

Spins a paramiko ServerInterface listening on 127.0.0.1:<rand>. The
server seeds a temp root with `alpha.nc` and `beta.nc`. SFTP requests
are served via the stdlib + paramiko's built-in SFTPServerInterface.

Reference: paramiko/demos/demo_server.py.
"""
from __future__ import annotations

import socket
import threading
from dataclasses import dataclass
from pathlib import Path

import paramiko
import pytest


_HOST_KEY = paramiko.RSAKey.generate(2048)


class _InMemoryServer(paramiko.ServerInterface):
    def __init__(self) -> None:
        self.event = threading.Event()

    def check_auth_password(self, username, password):
        if username == "testuser" and password == "testpass":
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def check_channel_request(self, kind, chanid):
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def get_allowed_auths(self, username):
        return "password"

    def check_channel_subsystem_request(self, channel, name):
        if name == "sftp":
            self.event.set()
            return True
        return False


def _run_server_thread(sock: socket.socket, root: str,
                        stop: threading.Event) -> None:
    while not stop.is_set():
        sock.settimeout(0.2)
        try:
            client_sock, _ = sock.accept()
        except socket.timeout:
            continue
        except OSError:
            return

        t = paramiko.Transport(client_sock)
        t.add_server_key(_HOST_KEY)
        t.set_subsystem_handler("sftp", paramiko.SFTPServer,
                                 _RootedSFTPHandler.with_root(root))
        server = _InMemoryServer()
        try:
            t.start_server(server=server)
        except paramiko.SSHException:
            continue
        # Keep transport alive until client disconnects.
        # (Background — main thread can keep accepting more clients.)
        threading.Thread(
            target=lambda: t.join(),
            daemon=True,
        ).start()


class _RootedSFTPHandler(paramiko.SFTPServerInterface):
    """SFTPServerInterface jailed to a fixture root.

    paramiko's built-in StubSFTPServer is the reference; this is the
    same shape, scoped tight to our test needs (listdir, open for
    read, stat).
    """
    _ROOT: str = ""

    @classmethod
    def with_root(cls, root: str) -> type["_RootedSFTPHandler"]:
        new = type("_RootedSFTPHandler_bound", (cls,), {"_ROOT": root})
        return new

    def _real(self, path: str) -> str:
        # paramiko gives us paths as the client sees them. Resolve under root.
        if path.startswith("/"):
            return str(Path(self._ROOT) / path.lstrip("/"))
        return str(Path(self._ROOT) / path)

    def list_folder(self, path):
        real = self._real(path)
        try:
            entries = []
            for name in sorted(Path(real).iterdir()):
                a = paramiko.SFTPAttributes.from_stat(name.stat(),
                                                      filename=name.name)
                entries.append(a)
            return entries
        except FileNotFoundError:
            return paramiko.SFTP_NO_SUCH_FILE
        except OSError:
            return paramiko.SFTP_FAILURE

    def stat(self, path):
        real = self._real(path)
        try:
            return paramiko.SFTPAttributes.from_stat(Path(real).stat())
        except FileNotFoundError:
            return paramiko.SFTP_NO_SUCH_FILE

    lstat = stat

    def open(self, path, flags, attr):
        real = self._real(path)
        try:
            f = open(real, "rb")
        except FileNotFoundError:
            return paramiko.SFTP_NO_SUCH_FILE
        h = paramiko.SFTPHandle(flags)
        h.readfile = f
        return h


@dataclass
class _InprocSSHDHandle:
    port: int
    root: str


@pytest.fixture
def inproc_sshd(tmp_path):
    """Yield a tuple (port, root) for an in-process sshd accepting
    user=testuser pass=testpass over SFTP."""
    root = tmp_path / "remote-root"
    root.mkdir()
    (root / "alpha.nc").write_bytes(b"\x89HDF\r\n\x1a\n" + b"\x00" * 32)
    (root / "beta.nc").write_bytes(b"\x89HDF\r\n\x1a\n" + b"\x01" * 32)
    (root / "skip.txt").write_text("not a netcdf")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.listen(8)

    stop = threading.Event()
    t = threading.Thread(target=_run_server_thread,
                          args=(sock, str(root), stop), daemon=True)
    t.start()
    try:
        yield _InprocSSHDHandle(port=port, root=str(root))
    finally:
        stop.set()
        try:
            sock.close()
        except Exception:
            pass
        t.join(timeout=3)
```

- [ ] **Step 4: Run test to verify it passes**

```
uv run pytest tests/ssh_broker/integration/test_inproc_sshd_fixture_smoke.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/ssh_broker/conftest.py tests/ssh_broker/integration/test_inproc_sshd_fixture_smoke.py
git commit -m "cycle-14 task 8: in-process paramiko sshd fixture for integration tests"
```

---

## Task 9: End-to-end broker round-trip integration test

**Files:**
- Create: `tests/ssh_broker/integration/test_inproc_sshd.py`

- [ ] **Step 1: Write the test**

```python
# tests/ssh_broker/integration/test_inproc_sshd.py
"""End-to-end: start broker server thread against in-proc sshd, do
JSON-RPC requests, verify each method end-to-end.

This is the "smoke that proves theme A holds together" test.
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
from src.ssh_broker.sftp_holder import SFTPHolder


def _round_trip(sock_path, req):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.connect(sock_path)
        s.sendall((json.dumps(req) + "\n").encode())
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(4096)
            if not chunk: break
            buf += chunk
        return json.loads(buf.decode())


def _start(holder, tmp_path):
    sock_path = str(tmp_path / "b.sock")
    stop = threading.Event()
    t = threading.Thread(target=serve_forever,
                          kwargs=dict(holder=holder, socket_path=sock_path,
                                      stop_event=stop), daemon=True)
    t.start()
    deadline = time.time() + 3
    while not Path(sock_path).exists():
        if time.time() > deadline: raise TimeoutError
        time.sleep(0.05)
    return sock_path, stop, t


def test_end_to_end_listdir_glob_get(inproc_sshd, tmp_path):
    # Real paramiko client against our in-proc sshd.
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect("127.0.0.1", port=inproc_sshd.port,
                    username="testuser", password="testpass",
                    allow_agent=False, look_for_keys=False)
    holder = SFTPHolder(client=client, host="127.0.0.1", user="testuser")

    sock_path, stop, t = _start(holder, tmp_path)
    try:
        # 1. ping
        r = _round_trip(sock_path, {"jsonrpc": "2.0", "id": 1,
                                      "method": "ping"})
        assert r["result"] == {"alive": True}

        # 2. listdir of the fixture root
        r = _round_trip(sock_path, {"jsonrpc": "2.0", "id": 2,
                                      "method": "listdir",
                                      "params": {"path": inproc_sshd.root}})
        names = {e["name"] for e in r["result"]["entries"]}
        assert "alpha.nc" in names and "beta.nc" in names

        # 3. glob *.nc
        r = _round_trip(sock_path, {"jsonrpc": "2.0", "id": 3,
                                      "method": "glob",
                                      "params": {"pattern":
                                                  f"{inproc_sshd.root}/*.nc"}})
        assert sorted(Path(p).name for p in r["result"]["paths"]) == \
            ["alpha.nc", "beta.nc"]

        # 4. get_chunk of alpha.nc first 8 bytes
        r = _round_trip(sock_path, {"jsonrpc": "2.0", "id": 4,
                                      "method": "get_chunk",
                                      "params": {
                                          "path":
                                              f"{inproc_sshd.root}/alpha.nc",
                                          "offset": 0, "length": 8}})
        data = base64.b64decode(r["result"]["data_b64"])
        assert data == b"\x89HDF\r\n\x1a\n"
    finally:
        stop.set()
        t.join(timeout=5)
        holder.close()
```

- [ ] **Step 2: Run test**

```
uv run pytest tests/ssh_broker/integration/test_inproc_sshd.py -v
```
Expected: 1 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/ssh_broker/integration/test_inproc_sshd.py
git commit -m "cycle-14 task 9: end-to-end broker round-trip against in-proc sshd"
```

---

## Task 10: Idle-shutdown and connection-lost integration tests

**Files:**
- Create: `tests/ssh_broker/integration/test_idle_shutdown.py`
- Create: `tests/ssh_broker/integration/test_connection_lost.py`

- [ ] **Step 1: Write the tests**

```python
# tests/ssh_broker/integration/test_idle_shutdown.py
"""Broker exits cleanly after idle-timeout with no activity."""
from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

from src.ssh_broker.server import serve_forever


def test_server_exits_after_idle_timeout(tmp_path):
    holder = MagicMock()
    holder.is_alive.return_value = True
    sock_path = str(tmp_path / "b.sock")
    stop = threading.Event()
    t = threading.Thread(target=serve_forever,
                          kwargs=dict(holder=holder, socket_path=sock_path,
                                      stop_event=stop,
                                      idle_timeout=0.5,
                                      poll_interval=0.1),
                          daemon=True)
    started = time.time()
    t.start()
    t.join(timeout=5)
    elapsed = time.time() - started
    assert not t.is_alive(), "server thread should have exited"
    # Allow some slop; should be well under 5s.
    assert elapsed < 4.0
    # Socket should be cleaned up.
    assert not Path(sock_path).exists()
```

```python
# tests/ssh_broker/integration/test_connection_lost.py
"""When holder.is_alive() flips False mid-session, broker responds
with CONNECTION_LOST and the user is expected to restart."""
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
        s.sendall((json.dumps(req) + "\n").encode())
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(4096)
            if not chunk: break
            buf += chunk
        return json.loads(buf.decode())


def test_connection_lost_returned_when_holder_dies(tmp_path):
    holder = MagicMock()
    # Alive at first, then dies.
    alive = [True]
    holder.is_alive.side_effect = lambda: alive[0]
    sock_path = str(tmp_path / "b.sock")
    stop = threading.Event()
    t = threading.Thread(target=serve_forever,
                          kwargs=dict(holder=holder, socket_path=sock_path,
                                      stop_event=stop), daemon=True)
    t.start()
    deadline = time.time() + 3
    while not Path(sock_path).exists():
        if time.time() > deadline: raise TimeoutError
        time.sleep(0.05)

    try:
        # First call succeeds.
        r1 = _round_trip(sock_path, {"jsonrpc": "2.0", "id": 1,
                                       "method": "ping"})
        assert r1["result"] == {"alive": True}

        # Holder dies.
        alive[0] = False

        # Second call returns CONNECTION_LOST.
        r2 = _round_trip(sock_path, {"jsonrpc": "2.0", "id": 2,
                                       "method": "ping"})
        assert r2["error"]["code"] == -32000
    finally:
        stop.set()
        t.join(timeout=5)
```

- [ ] **Step 2: Run tests**

```
uv run pytest tests/ssh_broker/integration/test_idle_shutdown.py tests/ssh_broker/integration/test_connection_lost.py -v
```
Expected: 2 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/ssh_broker/integration/test_idle_shutdown.py tests/ssh_broker/integration/test_connection_lost.py
git commit -m "cycle-14 task 10: idle-timeout + connection-lost integration tests"
```

---

## Task 11: Register broker as a plugin entry-point

**Files:**
- Modify: `build/claude-code/metplot/mcp-servers/netcdf_reader/pyproject.toml:27-28`
- Modify: `tests/targets/claude_code/test_mcp_smoke.py`

- [ ] **Step 1: Write the failing test (extend the existing smoke test)**

```python
# Append to tests/targets/claude_code/test_mcp_smoke.py
def test_ssh_broker_entry_point_registered(built_plugin):
    """Cycle 14 — metplot-ssh-broker CLI must be installable via the
    netcdf_reader bundle's pyproject.toml."""
    pp_text = (built_plugin / "mcp-servers" / "netcdf_reader"
                / "pyproject.toml").read_text()
    assert "metplot-ssh-broker" in pp_text, (
        "expected metplot-ssh-broker entry-point in netcdf_reader pyproject")
    assert "src.ssh_broker.cli:main" in pp_text, (
        "expected entry-point target src.ssh_broker.cli:main")
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/targets/claude_code/test_mcp_smoke.py::test_ssh_broker_entry_point_registered -v
```
Expected: FAIL — assertion error: "metplot-ssh-broker" not in pp_text.

- [ ] **Step 3: Add the entry-point**

Edit `build/claude-code/metplot/mcp-servers/netcdf_reader/pyproject.toml` — change:

```toml
[project.scripts]
metplot-netcdf-reader = "src.mcp.netcdf_reader.server:main"
```

to:

```toml
[project.scripts]
metplot-netcdf-reader = "src.mcp.netcdf_reader.server:main"
metplot-ssh-broker = "src.ssh_broker.cli:main"
```

- [ ] **Step 4: Run test to verify it passes**

```
uv run pytest tests/targets/claude_code/test_mcp_smoke.py::test_ssh_broker_entry_point_registered -v
```
Expected: 1 passed.

- [ ] **Step 5: Verify the full bundle smoke still works**

```
uv run pytest tests/targets/claude_code/test_mcp_smoke.py -v
```
Expected: all passed.

- [ ] **Step 6: Commit**

```bash
git add build/claude-code/metplot/mcp-servers/netcdf_reader/pyproject.toml tests/targets/claude_code/test_mcp_smoke.py
git commit -m "cycle-14 task 11: register metplot-ssh-broker entry-point in plugin bundle"
```

---

## Task 12: BrokerSFTPClient — the MCP-side client adapter

**Files:**
- Create: `src/mcp/netcdf_reader/paths/ssh_broker.py`
- Create: `tests/mcp/netcdf_reader/unit/test_ssh_broker_client.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/netcdf_reader/unit/test_ssh_broker_client.py
"""BrokerSFTPClient — talks JSON-RPC over a local UNIX socket.

Tests stand up a tiny in-proc mock server on a temp socket path and
verify the client's wire shape + result decoding.
"""
from __future__ import annotations

import base64
import json
import socket
import threading
from pathlib import Path

import pytest

from src.mcp.netcdf_reader.paths.ssh_broker import (
    BrokerSFTPClient, BrokerRPCError,
)


def _mock_server(sock_path: str, replies: dict[str, dict]):
    """Tiny server that pattern-matches on method name and replies."""
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    Path(sock_path).parent.mkdir(parents=True, exist_ok=True)
    if Path(sock_path).exists():
        Path(sock_path).unlink()
    srv.bind(sock_path)
    srv.listen(1)
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
                    c = conn.recv(4096)
                    if not c: break
                    buf += c
                req = json.loads(buf.decode())
                reply = replies.get(req["method"],
                                     {"jsonrpc": "2.0", "id": req["id"],
                                      "error": {"code": -32601, "message": "no"}})
                # patch in id
                reply = {**reply, "id": req["id"]}
                conn.sendall((json.dumps(reply) + "\n").encode())
        srv.close()
    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    return stop, t


def test_ping_round_trip(tmp_path):
    sock_path = str(tmp_path / "b.sock")
    stop, t = _mock_server(sock_path, {
        "ping": {"jsonrpc": "2.0", "result": {"alive": True}},
    })
    try:
        c = BrokerSFTPClient(socket_path=sock_path)
        assert c.ping() == {"alive": True}
    finally:
        stop.set()
        t.join(timeout=2)


def test_listdir_attr_returns_paramiko_like_attrs(tmp_path):
    sock_path = str(tmp_path / "b.sock")
    stop, t = _mock_server(sock_path, {
        "listdir": {"jsonrpc": "2.0", "result": {"entries": [
            {"name": "a.nc", "size": 10, "mode": 0o100644,
             "mtime": 1.0, "is_dir": False, "is_link": False},
            {"name": "b.nc", "size": 20, "mode": 0o100644,
             "mtime": 2.0, "is_dir": False, "is_link": False},
        ]}},
    })
    try:
        c = BrokerSFTPClient(socket_path=sock_path)
        attrs = c.listdir_attr("/d")
        assert [a.filename for a in attrs] == ["a.nc", "b.nc"]
        assert attrs[0].st_size == 10
    finally:
        stop.set()
        t.join(timeout=2)


def test_glob_remote_returns_paths(tmp_path):
    sock_path = str(tmp_path / "b.sock")
    stop, t = _mock_server(sock_path, {
        "glob": {"jsonrpc": "2.0", "result": {"paths":
            ["/d/a.nc", "/d/b.nc"]}},
    })
    try:
        c = BrokerSFTPClient(socket_path=sock_path)
        assert c.glob_remote("/d/*.nc") == ["/d/a.nc", "/d/b.nc"]
    finally:
        stop.set()
        t.join(timeout=2)


def test_get_writes_local_file(tmp_path):
    sock_path = str(tmp_path / "b.sock")
    local = str(tmp_path / "out.nc")
    # The "get" method is mapped to RPC `get_chunk` + write loop, OR
    # `get_full`. Per protocol it uses get_full.
    stop, t = _mock_server(sock_path, {
        "get_full": {"jsonrpc": "2.0", "result":
            {"bytes_copied": 5, "sha256": "deadbeef"}},
    })
    try:
        c = BrokerSFTPClient(socket_path=sock_path)
        info = c.get("/remote.nc", local)
        assert info == {"bytes_copied": 5, "sha256": "deadbeef"}
    finally:
        stop.set()
        t.join(timeout=2)


def test_error_response_raises_broker_rpc_error(tmp_path):
    sock_path = str(tmp_path / "b.sock")
    stop, t = _mock_server(sock_path, {
        "listdir": {"jsonrpc": "2.0", "error":
            {"code": -32001, "message": "not found: /nope"}},
    })
    try:
        c = BrokerSFTPClient(socket_path=sock_path)
        with pytest.raises(BrokerRPCError) as ei:
            c.listdir_attr("/nope")
        assert ei.value.code == -32001
        assert "not found" in ei.value.message
    finally:
        stop.set()
        t.join(timeout=2)
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/mcp/netcdf_reader/unit/test_ssh_broker_client.py -v
```
Expected: FAIL — module not found.

- [ ] **Step 3: Implement BrokerSFTPClient**

```python
# src/mcp/netcdf_reader/paths/ssh_broker.py
"""Client-side adapter that lets the MCP talk to a running broker.

Mimics enough of paramiko.SFTPClient that adapter.open() can swap
implementations transparently. NEVER opens a paramiko transport —
all SSH/SFTP work happens in the broker process.
"""
from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from typing import Any

from src.ssh_broker.protocol import (
    decode_line, encode_message, make_request,
)


class BrokerRPCError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


@dataclass
class _LikeSFTPAttributes:
    """Stand-in for paramiko.SFTPAttributes, with the fields the MCP
    actually reads (filename / st_size / st_mode / st_mtime)."""
    filename: str
    st_size: int
    st_mode: int
    st_mtime: float


class BrokerSFTPClient:
    def __init__(self, socket_path: str) -> None:
        self.socket_path = socket_path
        self._req_id = 0

    def _call(self, method: str, params: dict[str, Any] | None = None
              ) -> dict[str, Any]:
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

    # ── paramiko.SFTPClient compatible surface ──────────────────────

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

    # ── Broker extension: remote glob ───────────────────────────────

    def glob_remote(self, pattern: str) -> list[str]:
        r = self._call("glob", {"pattern": pattern})
        return list(r["paths"])
```

- [ ] **Step 4: Run test to verify it passes**

```
uv run pytest tests/mcp/netcdf_reader/unit/test_ssh_broker_client.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf_reader/paths/ssh_broker.py tests/mcp/netcdf_reader/unit/test_ssh_broker_client.py
git commit -m "cycle-14 task 12: BrokerSFTPClient — MCP-side JSON-RPC client over UNIX socket"
```

---

## Task 13: open_ssh_with_broker_fallback + paths/ssh.py extension

**Files:**
- Modify: `src/mcp/netcdf_reader/paths/ssh.py` (append at end of file)
- Create: `tests/mcp/netcdf_reader/unit/test_open_ssh_with_broker_fallback.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/netcdf_reader/unit/test_open_ssh_with_broker_fallback.py
"""open_ssh_with_broker_fallback dispatch:
- broker socket present + ping ok → returns BrokerSFTPClient
- broker socket absent → returns None (caller falls back to paramiko)
- broker socket present but ping fails → returns None
"""
from __future__ import annotations

import socket
from pathlib import Path

import pytest

from src.mcp.netcdf_reader.paths.ssh import (
    discover_broker_socket, open_ssh_with_broker_fallback,
)


def test_discover_broker_socket_returns_path_when_present(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    sock_dir = tmp_path / "metplot-ssh"
    sock_dir.mkdir()
    sock_path = sock_dir / "h.example.sock"
    # Create as a UNIX socket
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(str(sock_path))
    try:
        found = discover_broker_socket("h.example")
        assert found == str(sock_path)
    finally:
        s.close()
        sock_path.unlink(missing_ok=True)


def test_discover_broker_socket_returns_none_when_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    assert discover_broker_socket("nope.example") is None


def test_open_ssh_with_broker_fallback_returns_none_no_socket(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    out = open_ssh_with_broker_fallback("h.example")
    assert out is None


def test_open_ssh_with_broker_fallback_returns_client_when_ping_ok(
    monkeypatch, tmp_path,
):
    import json
    import threading
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    sock_dir = tmp_path / "metplot-ssh"
    sock_dir.mkdir()
    sock_path = str(sock_dir / "h.example.sock")
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(sock_path)
    srv.listen(1)
    def _serve():
        srv.settimeout(2)
        try:
            conn, _ = srv.accept()
            with conn:
                conn.recv(4096)
                conn.sendall((json.dumps({"jsonrpc": "2.0", "id": 1,
                                            "result": {"alive": True}}) + "\n")
                             .encode())
        except socket.timeout:
            pass
    th = threading.Thread(target=_serve, daemon=True)
    th.start()
    try:
        out = open_ssh_with_broker_fallback("h.example")
        assert out is not None
        # It should be a BrokerSFTPClient (duck-typed).
        assert hasattr(out, "listdir_attr")
    finally:
        srv.close()
        Path(sock_path).unlink(missing_ok=True)
        th.join(timeout=2)
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/mcp/netcdf_reader/unit/test_open_ssh_with_broker_fallback.py -v
```
Expected: FAIL — `discover_broker_socket` / `open_ssh_with_broker_fallback` not importable.

- [ ] **Step 3: Append helpers to `paths/ssh.py`**

Append to the end of `src/mcp/netcdf_reader/paths/ssh.py`:

```python


# ── Cycle 14: Broker integration ────────────────────────────────

def _broker_socket_dir() -> str:
    """The directory we expect brokers to register sockets in."""
    import os
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        return os.path.join(runtime, "metplot-ssh")
    return "/tmp/metplot-ssh"


def discover_broker_socket(host: str) -> str | None:
    """Return the path of a running broker's socket for `host`, or None."""
    from pathlib import Path
    p = Path(_broker_socket_dir()) / f"{host}.sock"
    if p.exists():
        # Socket files are AF_UNIX endpoints — `exists()` is enough.
        return str(p)
    return None


def open_ssh_with_broker_fallback(host: str):
    """If a broker socket is present and answers ping, return a
    BrokerSFTPClient. Else return None — caller falls back to direct
    paramiko (cycle-12 behavior).
    """
    sock = discover_broker_socket(host)
    if sock is None:
        return None
    # Lazy import to avoid cycle-12 callers paying the cost.
    from src.mcp.netcdf_reader.paths.ssh_broker import (
        BrokerRPCError, BrokerSFTPClient,
    )
    client = BrokerSFTPClient(socket_path=sock)
    try:
        client.ping()
    except (OSError, BrokerRPCError):
        return None
    return client
```

- [ ] **Step 4: Run test to verify it passes**

```
uv run pytest tests/mcp/netcdf_reader/unit/test_open_ssh_with_broker_fallback.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf_reader/paths/ssh.py tests/mcp/netcdf_reader/unit/test_open_ssh_with_broker_fallback.py
git commit -m "cycle-14 task 13: open_ssh_with_broker_fallback in paths/ssh.py"
```

---

## Task 14: Adapter routing through the broker

**Files:**
- Modify: `src/mcp/netcdf_reader/adapter.py:62-110`
- Create: `tests/mcp/netcdf_reader/unit/test_adapter_broker_routing.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/netcdf_reader/unit/test_adapter_broker_routing.py
"""adapter.open() routes ssh:// through the broker when available."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import xarray as xr

from src.mcp.netcdf_reader.adapter import NetCDFAdapter


def test_adapter_open_uses_broker_when_present():
    a = NetCDFAdapter()
    # Simulate the broker client returning a file-like object via get().
    fake_broker = MagicMock()
    fake_broker.get.return_value = {"bytes_copied": 10, "sha256": "x"}
    with patch("src.mcp.netcdf_reader.paths.ssh."
                "open_ssh_with_broker_fallback",
                return_value=fake_broker) as fallback_mock, \
         patch.object(a, "_open_via_broker",
                       return_value=xr.Dataset()) as broker_open:
        ds = a.open(["ssh://home.example/file.nc"])
        assert isinstance(ds, xr.Dataset)
        fallback_mock.assert_called_with("home.example")
        broker_open.assert_called_once()


def test_adapter_open_falls_back_to_paramiko_when_no_broker():
    """When the broker isn't running, the cycle-12 paramiko path
    (which prompts for credentials at the MCP layer) must still run."""
    a = NetCDFAdapter()
    with patch("src.mcp.netcdf_reader.paths.ssh."
                "open_ssh_with_broker_fallback", return_value=None), \
         patch("src.mcp.netcdf_reader.paths.ssh.silent_auth_chain") \
             as auth_mock:
        # Make silent_auth raise so we can verify it was the path taken.
        from src.mcp.netcdf_reader.paths.ssh import SSHAuthNeeded, SSHConfig
        auth_mock.side_effect = SSHAuthNeeded(
            cfg=SSHConfig(host="home.example"), attempts=[],
        )
        # The inspect layer would normally catch and convert this; here
        # we just want to assert auth_mock was called.
        try:
            a.open(["ssh://home.example/file.nc"])
        except SSHAuthNeeded:
            pass
        auth_mock.assert_called()
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/mcp/netcdf_reader/unit/test_adapter_broker_routing.py -v
```
Expected: FAIL — `NetCDFAdapter._open_via_broker` not defined.

- [ ] **Step 3: Modify adapter.py**

Edit `src/mcp/netcdf_reader/adapter.py`. In the SSH branch (around line 78-106), insert a broker check before the existing paramiko path. Add a `_open_via_broker` method on the class.

Find this block:
```python
            if cls.kind == PathKind.SSH_REMOTE:
                from src.mcp.netcdf_reader.paths.ssh import (
                    SSHConfig, parse_ssh_config_for_host,
                    silent_auth_chain, connect_explicit, open_sftp_file,
                )
                assert cls.host is not None
                assert cls.remote_path is not None
```

Replace with:
```python
            if cls.kind == PathKind.SSH_REMOTE:
                from src.mcp.netcdf_reader.paths.ssh import (
                    SSHConfig, parse_ssh_config_for_host,
                    silent_auth_chain, connect_explicit, open_sftp_file,
                    open_ssh_with_broker_fallback,
                )
                assert cls.host is not None
                assert cls.remote_path is not None
                # Cycle 14: prefer broker if available.
                broker = open_ssh_with_broker_fallback(cls.host)
                if broker is not None:
                    return self._open_via_broker(broker, cls.remote_path)
```

Then add the new method on `NetCDFAdapter` (near the existing `open` method):
```python
    def _open_via_broker(self, broker, remote_path: str) -> xr.Dataset:
        """Stage the remote file locally via the broker, then open."""
        import tempfile
        from pathlib import Path as _Path
        with tempfile.NamedTemporaryFile(
            prefix="metplot-broker-", suffix=_Path(remote_path).suffix,
            delete=False,
        ) as tmp:
            local = tmp.name
        broker.get(remote_path, local)
        return _open_with_decode_fallback(
            lambda decode: xr.open_dataset(
                local, decode_times=decode, chunks="auto"))
```

- [ ] **Step 4: Run test to verify it passes**

```
uv run pytest tests/mcp/netcdf_reader/unit/test_adapter_broker_routing.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Verify existing SSH tests still pass (cycle-12 fallback path unchanged)**

```
uv run pytest tests/mcp/netcdf_reader/unit/test_ssh_explicit_auth.py tests/mcp/netcdf_reader/unit/test_ssh_silent_auth.py tests/mcp/netcdf_reader/unit/test_ssh_inspect.py -v
```
Expected: all passed.

- [ ] **Step 6: Commit**

```bash
git add src/mcp/netcdf_reader/adapter.py tests/mcp/netcdf_reader/unit/test_adapter_broker_routing.py
git commit -m "cycle-14 task 14: adapter routes ssh:// through broker when present, falls back to paramiko"
```

---

## Task 15: SSH-glob classification via broker

**Files:**
- Modify: `src/mcp/netcdf_reader/paths/classify.py:16-21` (add SSH_MULTI) and `48-62` (ssh-glob branch)
- Create: `tests/mcp/netcdf_reader/unit/test_ssh_classify_glob.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/netcdf_reader/unit/test_ssh_classify_glob.py
"""ssh://host/path/*.nc should expand through the broker."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.mcp.netcdf_reader.paths.classify import (
    ClassifyError, PathKind, classify,
)


def test_ssh_url_without_glob_still_returns_ssh_remote():
    k = classify("ssh://host/path/file.nc")
    assert k.kind == PathKind.SSH_REMOTE
    assert k.paths == []  # paths populated only for *_MULTI kinds


def test_ssh_glob_calls_broker_and_returns_ssh_multi():
    broker = MagicMock()
    broker.glob_remote.return_value = [
        "/data/a.nc", "/data/b.nc",
    ]
    with patch("src.mcp.netcdf_reader.paths.ssh."
                "open_ssh_with_broker_fallback", return_value=broker):
        k = classify("ssh://host/data/*.nc")
    assert k.kind == PathKind.SSH_MULTI
    assert k.host == "host"
    assert k.paths == [
        "ssh://host/data/a.nc",
        "ssh://host/data/b.nc",
    ]
    broker.glob_remote.assert_called_with("/data/*.nc")


def test_ssh_glob_without_broker_raises_broker_required():
    with patch("src.mcp.netcdf_reader.paths.ssh."
                "open_ssh_with_broker_fallback", return_value=None):
        with pytest.raises(ClassifyError) as ei:
            classify("ssh://host/data/*.nc")
        assert "broker_required" in str(ei.value)
        assert "metplot-ssh-broker host" in str(ei.value)


def test_ssh_glob_empty_match_raises_clean_error():
    broker = MagicMock()
    broker.glob_remote.return_value = []
    with patch("src.mcp.netcdf_reader.paths.ssh."
                "open_ssh_with_broker_fallback", return_value=broker):
        with pytest.raises(ClassifyError) as ei:
            classify("ssh://host/data/*.nc")
        assert "no remote files matched" in str(ei.value)
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/mcp/netcdf_reader/unit/test_ssh_classify_glob.py -v
```
Expected: FAIL — `PathKind.SSH_MULTI` not defined; ssh-glob still returns SSH_REMOTE.

- [ ] **Step 3: Modify classify.py**

Edit `src/mcp/netcdf_reader/paths/classify.py`.

First, extend `PathKind` (around line 16-21):
```python
class PathKind:
    LOCAL_SINGLE = "local_single"
    LOCAL_MULTI = "local_multi"
    REMOTE_URL = "remote_url"
    SSH_REMOTE = "ssh_remote"
    SSH_MULTI = "ssh_multi"  # cycle 14
```

Then in `classify()`, replace the SSH branch (around line 48-62):
```python
def classify(raw: str) -> ClassifiedPath:
    if raw.startswith("ssh://"):
        m = _SSH_RE.match(raw)
        if not m:
            raise ClassifyError(f"malformed ssh URL: {raw!r}")
        port = int(m.group("port")) if m.group("port") else None
        host = m.group("host")
        remote_path = m.group("path")
        # Cycle 14: ssh-glob expansion via broker.
        if _has_glob(remote_path):
            from src.mcp.netcdf_reader.paths.ssh import (
                open_ssh_with_broker_fallback,
            )
            broker = open_ssh_with_broker_fallback(host)
            if broker is None:
                raise ClassifyError(
                    f"broker_required: remote glob expansion for "
                    f"{raw!r} requires a running metplot-ssh broker. "
                    f"Run `metplot-ssh-broker {host}` in your terminal "
                    f"first.")
            matches = broker.glob_remote(remote_path)
            if not matches:
                raise ClassifyError(
                    f"no remote files matched glob: {raw!r}")
            user_prefix = ""
            if m.group("user"):
                user_prefix = m.group("user") + "@"
            port_suffix = f":{port}" if port else ""
            ssh_paths = [
                f"ssh://{user_prefix}{host}{port_suffix}{p}"
                for p in matches
            ]
            return ClassifiedPath(
                kind=PathKind.SSH_MULTI, scheme="ssh",
                user=m.group("user"), host=host, port=port,
                paths=ssh_paths, raw=raw,
            )
        return ClassifiedPath(
            kind=PathKind.SSH_REMOTE,
            scheme="ssh",
            user=m.group("user"),
            host=host,
            port=port,
            remote_path=remote_path,
            raw=raw,
        )
    # ... rest of the function unchanged ...
```

- [ ] **Step 4: Run test to verify it passes**

```
uv run pytest tests/mcp/netcdf_reader/unit/test_ssh_classify_glob.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Run existing classify tests to confirm no regression**

```
uv run pytest tests/mcp/netcdf_reader/unit/test_classify.py -v
```
Expected: all previously-passing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add src/mcp/netcdf_reader/paths/classify.py tests/mcp/netcdf_reader/unit/test_ssh_classify_glob.py
git commit -m "cycle-14 task 15: SSH_MULTI + broker-backed remote glob expansion"
```

---

## Task 16: broker_required envelope in inspect()

**Files:**
- Modify: `src/mcp/netcdf_reader/tools/inspect.py` — wrap `ClassifyError` catch to convert `broker_required:` prefix into envelope
- Create: `tests/mcp/netcdf_reader/unit/test_inspect_broker_required.py`

- [ ] **Step 1: Locate the existing ClassifyError handling in inspect.py**

Run:
```
grep -n "ClassifyError\|ambiguous\|ssh_auth_needed" src/mcp/netcdf_reader/tools/inspect.py | head -20
```
Use the line numbers to find where ClassifyError is currently caught.

- [ ] **Step 2: Write the failing test**

```python
# tests/mcp/netcdf_reader/unit/test_inspect_broker_required.py
"""inspect() returns a broker_required ambiguous envelope when an
ssh-glob is requested but no broker is running."""
from __future__ import annotations

from unittest.mock import patch

from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.inspect import inspect as _inspect


def test_inspect_returns_broker_required_envelope():
    with patch("src.mcp.netcdf_reader.paths.ssh."
                "open_ssh_with_broker_fallback", return_value=None):
        env = _inspect(adapter=NetCDFAdapter(),
                        path="ssh://home.example/data/*.nc")
    assert env["ok"] is False
    assert env["error"]["code"] == "ambiguous"
    assert env["error"]["subcode"] == "broker_required"
    assert "metplot-ssh-broker home.example" in env["error"]["prompt"]
```

- [ ] **Step 3: Run test to verify it fails**

```
uv run pytest tests/mcp/netcdf_reader/unit/test_inspect_broker_required.py -v
```
Expected: FAIL — current ClassifyError handling probably bubbles as internal_error.

- [ ] **Step 4: Patch inspect.py**

Locate the ClassifyError catch block (use grep output from Step 1). It probably looks like:

```python
        except ClassifyError as e:
            return _envelope_error("file_not_found", str(e), {"path": path})
```

Replace with:

```python
        except ClassifyError as e:
            msg = str(e)
            if msg.startswith("broker_required:"):
                # Cycle 14: ssh-glob without a running broker.
                host = path.split("://", 1)[1].split("/", 1)[0].split("@")[-1]
                return {
                    "ok": False,
                    "error": {
                        "code": "ambiguous",
                        "subcode": "broker_required",
                        "message": msg,
                        "candidates": [
                            {"value": "start_broker",
                             "label": f"Run `metplot-ssh-broker {host}` "
                                       f"in your terminal first",
                             "param": "broker_socket",
                             "sensitive": False,
                             "evidence": [],
                             "confidence": 1.0},
                        ],
                        "prompt": (
                            f"Remote glob expansion requires a running "
                            f"broker. Run `metplot-ssh-broker {host}` in "
                            f"your terminal, then retry this inspect."
                        ),
                        "retry_with_param": "broker_socket",
                        "context": {"host": host, "path": path},
                    },
                    "warnings": [],
                }
            return _envelope_error("file_not_found", msg, {"path": path})
```

- [ ] **Step 5: Run test to verify it passes**

```
uv run pytest tests/mcp/netcdf_reader/unit/test_inspect_broker_required.py -v
```
Expected: 1 passed.

- [ ] **Step 6: Run all existing inspect tests**

```
uv run pytest tests/mcp/netcdf_reader/unit/test_ssh_inspect.py -v
```
Expected: all passed.

- [ ] **Step 7: Commit**

```bash
git add src/mcp/netcdf_reader/tools/inspect.py tests/mcp/netcdf_reader/unit/test_inspect_broker_required.py
git commit -m "cycle-14 task 16: broker_required envelope guides users to start the broker"
```

---

## Task 17: End-to-end inspect() through the broker

**Files:**
- Create: `tests/mcp/netcdf_reader/integration/test_inspect_via_broker.py`

- [ ] **Step 1: Write the test**

```python
# tests/mcp/netcdf_reader/integration/test_inspect_via_broker.py
"""End-to-end: in-proc sshd + broker server thread + inspect() call.

Validates the whole chain: classify → adapter → broker.get → xarray.
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from unittest.mock import patch

import paramiko
import pytest
import xarray as xr

pytest.importorskip("h5netcdf")

from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.inspect import inspect as _inspect
from src.ssh_broker.server import serve_forever
from src.ssh_broker.sftp_holder import SFTPHolder


def _write_minimal_netcdf(path: str) -> None:
    """Write a tiny but valid NetCDF file using xarray."""
    ds = xr.Dataset(
        {"t2m": (("time", "lat", "lon"),
                  [[[1.0, 2.0], [3.0, 4.0]]])},
        coords={"time": [0.0], "lat": [10.0, 20.0], "lon": [100.0, 200.0]},
    )
    ds.to_netcdf(path, engine="h5netcdf")


def test_inspect_via_broker_round_trip(inproc_sshd, tmp_path, monkeypatch):
    # Replace the fixture's alpha.nc with a real NetCDF.
    target = Path(inproc_sshd.root) / "alpha.nc"
    target.unlink()
    _write_minimal_netcdf(str(target))

    # Connect a real paramiko client to the in-proc sshd.
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect("127.0.0.1", port=inproc_sshd.port,
                    username="testuser", password="testpass",
                    allow_agent=False, look_for_keys=False)
    holder = SFTPHolder(client=client, host="127.0.0.1", user="testuser")

    # Start broker server on a temp socket where the discovery logic
    # will find it.
    sock_dir = tmp_path / "metplot-ssh"
    sock_dir.mkdir()
    sock_path = str(sock_dir / "127.0.0.1.sock")
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))

    stop = threading.Event()
    th = threading.Thread(target=serve_forever,
                           kwargs=dict(holder=holder, socket_path=sock_path,
                                       stop_event=stop), daemon=True)
    th.start()
    deadline = time.time() + 3
    while not Path(sock_path).exists():
        if time.time() > deadline:
            raise TimeoutError
        time.sleep(0.05)

    try:
        env = _inspect(
            adapter=NetCDFAdapter(),
            path=f"ssh://127.0.0.1{target}",
        )
        assert env["ok"] is True, env.get("error")
        # Should have the t2m variable.
        var_names = {v["name"] for v in env["result"]["variables"]}
        assert "t2m" in var_names
    finally:
        stop.set()
        th.join(timeout=5)
        holder.close()
```

- [ ] **Step 2: Run test**

```
uv run pytest tests/mcp/netcdf_reader/integration/test_inspect_via_broker.py -v
```
Expected: 1 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/mcp/netcdf_reader/integration/test_inspect_via_broker.py
git commit -m "cycle-14 task 17: end-to-end inspect() through broker + in-proc sshd"
```

---

## Task 18: netcdf-remote skill

**Files:**
- Create: `src/skills/netcdf-remote/SKILL.md`

- [ ] **Step 1: Write the skill**

```markdown
---
name: netcdf-remote
description: Guide users to set up the metplot-ssh-broker when an ssh:// path is requested. Use whenever a NetCDF path starts with ssh:// for the first time in a session, OR when the netcdf-reader MCP returns a broker_required envelope. Walks the user through the one-time setup so the credential never enters the AI's context.
---

# netcdf-remote

## When to use

- The user gives a path starting with `ssh://` and you haven't checked
  for a broker socket yet this session.
- The MCP returns an envelope with `error.subcode == "broker_required"`.
- The user is frustrated about being asked for SSH credentials in chat
  and wants a way to avoid it.

## Why the broker exists

**Without it:** typing an SSH passcode into the chat exposes it to
prompt-cache, telemetry, and conversation logs. On OTP-protected hosts
(OLCF, ALCF, NERSC) the passcode is also single-use, so the next MCP
call would prompt again.

**With it:** the user runs `metplot-ssh-broker <host>` in their own
terminal **before** launching the AI target, enters the passcode there
(`getpass.getpass()` — never echoes, never logs), and the broker
authenticates once. The credential is dropped from memory immediately
after `paramiko.connect()` returns. All subsequent MCP calls reuse the
authenticated SFTP channel via a local 0600 UNIX socket.

## Quick reference

1. Parse the host out of the user's `ssh://<user>@<host>[:port]/<path>` URL.
2. Try to call any `ssh://` tool. If the envelope returns
   `error.subcode == "broker_required"`, advance to step 3.
3. Surface this short message to the user, verbatim:

   > **Set up the metplot SSH broker once, in your own terminal:**
   >
   > ```
   > metplot-ssh-broker <host>
   > ```
   >
   > You'll enter your passcode there — it stays in your terminal and
   > never enters this chat. Leave the broker running (Ctrl-C when
   > you're done). Then come back and tell me to retry.

4. After the user confirms the broker is running, retry the original
   tool call. The MCP auto-detects the socket at
   `$XDG_RUNTIME_DIR/metplot-ssh/<host>.sock`.

## Pitfalls

- **One broker per host.** A user wanting two remotes runs two brokers
  in two terminals.
- **No auto-reconnect.** If the broker reports `connection_lost`, the
  user has to restart it (re-entering the passcode). The broker
  cannot reconnect on its own because it discarded the credential.
- **OLCF MaxSessions=1.** The broker is designed for this — it holds
  one SFTP channel and multiplexes all file ops at the SFTP protocol
  level. Compatible without configuration.
- **No remote exec.** The broker is SFTP-only. Remote command
  execution would need a second session channel, which OLCF refuses.
- **`broker_required` is informational, not an error.** Don't retry
  on a loop — surface the setup message and wait for the user.

## See also

- `netcdf-inspect` — what to do after the broker is set up
- `docs/architecture/ssh-broker.md` — protocol + threat model
```

- [ ] **Step 2: Verify the skill file is well-formed (lint-style check)**

```
head -5 src/skills/netcdf-remote/SKILL.md
```
Expected: starts with `---\nname: netcdf-remote\n...`.

- [ ] **Step 3: Commit**

```bash
git add src/skills/netcdf-remote/SKILL.md
git commit -m "cycle-14 task 18: netcdf-remote skill — guides users through broker setup"
```

---

## Task 19: Update netcdf-inspect skill to reference netcdf-remote

**Files:**
- Modify: `src/skills/netcdf-inspect/SKILL.md`

- [ ] **Step 1: Read the relevant section of netcdf-inspect**

```
sed -n '13,30p' src/skills/netcdf-inspect/SKILL.md
```
Locate the "Quick reference" step 2 — currently says "If the response envelope is `ok: false` with subcode `ssh_auth_needed`, prompt the user for SSH credentials...".

- [ ] **Step 2: Edit the file**

Find the line:
```
2. If the response envelope is `ok: false` with subcode `ssh_auth_needed`,
   prompt the user for SSH credentials per the candidates list, then retry
   with `ssh_config={user, host, port, auth: {...}}`.
```

Replace with:
```
2. If the response envelope is `ok: false`:
   - subcode `ssh_auth_needed` → defer to the `netcdf-remote` skill
     (cycle 14) which guides the user to start `metplot-ssh-broker` in
     their own terminal, avoiding any in-chat passcode entry.
   - subcode `broker_required` → also defer to `netcdf-remote`. The MCP
     is telling you remote glob expansion needs a broker socket.
   - any other subcode → surface to the user verbatim and stop.
```

- [ ] **Step 3: Commit**

```bash
git add src/skills/netcdf-inspect/SKILL.md
git commit -m "cycle-14 task 19: netcdf-inspect points at netcdf-remote for SSH/broker flows"
```

---

## Task 20: README — Remote file access subsection

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Find the right insertion point**

```
grep -n "## " README.md | head -30
```

Insert under "Targets" or "Capabilities" — wherever feels closest to other access-method documentation.

- [ ] **Step 2: Add the new subsection**

Append this block after the most appropriate existing section header (use `Edit` with explicit context to place it correctly):

```markdown
### Remote file access (OLCF and other OTP-protected hosts)

For NetCDF files on hosts that require interactive auth (RSA SecurID
passcode, Duo PIN+token, etc.) — like OLCF's `home.ccs.ornl.gov` — use
the **metplot-ssh-broker** so your credential never enters the AI's
context.

**One-time setup in your own terminal, BEFORE launching Claude Code:**

```bash
metplot-ssh-broker home.ccs.ornl.gov
```

You'll be prompted for your passcode. The broker:
- reads the passcode via `getpass.getpass()` (never echoes, never logs)
- authenticates once via paramiko
- **drops the passcode from memory immediately** after `connect()`
- opens ONE SFTP channel and reuses it for all subsequent file ops
  (compatible with `MaxSessions=1` policies)
- exposes a `0600` UNIX socket at
  `$XDG_RUNTIME_DIR/metplot-ssh/<host>.sock`

**Then launch Claude Code.** Any `ssh://<host>/path` reference in your
prompts is automatically routed through the broker — no credential
enters the chat. When you're done, `Ctrl-C` the broker.

**Limits:**
- SFTP only — no remote command execution
- One broker per host — run multiple brokers for multiple remotes
- No auto-reconnect — if the connection dies, restart the broker
  (and re-enter the passcode in your terminal)

See `docs/architecture/ssh-broker.md` for the full design.
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "cycle-14 task 20: README — Remote file access (OLCF) subsection"
```

---

## Task 21: Architecture doc

**Files:**
- Create: `docs/architecture/ssh-broker.md`

- [ ] **Step 1: Write the doc**

```markdown
# SSH Broker Architecture

## Goal

Authenticate to an OTP-protected SSH host **once in the user's
terminal**, before launching any AI tool, and reuse that authenticated
SFTP channel from inside the metplot MCP. The credential never crosses
the AI boundary.

## Components

```
┌────────────────┐    one TCP + one SFTP channel    ┌─────────────────┐
│ metplot-ssh-   │─────────────────────────────────▶│ remote sshd     │
│ broker         │   keepalive every 30s            │ (e.g. OLCF)     │
│ (Python CLI)   │                                   └─────────────────┘
│                │
│ paramiko       │
│ SSHClient +    │
│ SFTPClient     │
└────────────────┘
        ▲
        │ JSON-RPC 2.0 over UNIX domain socket
        │ $XDG_RUNTIME_DIR/metplot-ssh/<host>.sock (mode 0600)
        ▼
┌────────────────┐
│ Claude Code +  │   no SSH knowledge, no credential
│ metplot MCP    │   only knows the socket path
└────────────────┘
```

## Protocol

Newline-delimited JSON-RPC 2.0 over `AF_UNIX SOCK_STREAM`.

**Request:**
```json
{"jsonrpc":"2.0","id":N,"method":"...","params":{...}}
```

**Response:**
```json
{"jsonrpc":"2.0","id":N,"result":{...}}
```

**Error:**
```json
{"jsonrpc":"2.0","id":N,"error":{"code":int,"message":str}}
```

### Methods

| Method | Params | Result |
|---|---|---|
| `ping` | `{}` | `{"alive": true}` |
| `listdir` | `{"path": str}` | `{"entries": [{name, size, mode, mtime, is_dir, is_link}, ...]}` |
| `stat` | `{"path": str}` | `{"entry": {...}}` |
| `glob` | `{"pattern": str}` | `{"paths": [str, ...]}` |
| `get_chunk` | `{"path": str, "offset": int, "length": int}` | `{"data_b64": str, "size": int}` |
| `get_full` | `{"remote_path": str, "local_path": str}` | `{"bytes_copied": int, "sha256": str}` |

### Error codes

| Code | Meaning |
|---|---|
| -32700 | Parse error (malformed JSON) |
| -32600 | Invalid request |
| -32601 | Method not found |
| -32602 | Invalid params (missing required field) |
| -32603 | Internal error |
| -32000 | Connection lost (transport dropped) |
| -32001 | SFTP error (remote file ops) |

## Lifecycle

1. User invokes `metplot-ssh-broker <host>` in their terminal.
2. `getpass.getpass()` reads the passcode from `/dev/tty` (no echo, no
   log).
3. `paramiko.SSHClient.connect(password=<passcode>, ...)` opens the TCP
   transport and authenticates.
4. The passcode local variable falls out of scope (Python str is
   immutable so we can't zero the buffer; we minimize lifetime instead).
5. `SSHClient.open_sftp()` creates ONE SFTP channel. This is the **only
   SSH session channel the broker will ever open** — compatible with
   `MaxSessions=1`.
6. UNIX socket bound at the discovery path, mode `0600`.
7. Server loop accepts clients; dispatches each request to a method;
   sends the response.
8. On idle-timeout, `Ctrl-C`, `SIGTERM`, or connection-lost: close
   SFTP → close SSHClient → unlink socket → exit.

## Threat model

| Threat | Mitigation |
|---|---|
| Credential leaks into AI prompt/log/cache | Credential is never visible to the AI. Read in user's terminal via `getpass`, passed once to paramiko, dropped. |
| Credential persists on disk | No `--save` option; no env var prompt; no log mention. Credential lives only in process memory during `connect()`. |
| Local privilege escalation via socket | Socket mode `0600`, owned by `$UID`, in `$XDG_RUNTIME_DIR` (user-private). Connecting requires the same UID. |
| Replay of in-flight RPC traffic | UNIX-domain socket on the local host. No network exposure. |
| Server-side session multiplexing limits | One SFTP channel + protocol-level multiplexing. Validated against OLCF `MaxSessions=1`. |
| Connection death undetected by MCP | `transport.is_active()` checked on every request; broker returns `CONNECTION_LOST` and exits within ~5 seconds. |
| Two brokers race on the same socket path | CLI errors out if the socket already exists. |

## Discovery contract

The MCP looks for a socket at:

1. `$XDG_RUNTIME_DIR/metplot-ssh/<host>.sock` (if `XDG_RUNTIME_DIR` set)
2. `/tmp/metplot-ssh/<host>.sock` (fallback)

The broker creates the socket; the MCP reads it. No registry, no DNS,
no service discovery — just convention.

## Non-goals

- Auto-reconnect after `connection_lost` (would require persistent
  credential storage)
- Remote command execution (would need a second session channel; OLCF
  refuses)
- Multi-host broker (one process per remote; multi-host is cycle 15+)
- Windows named-pipe transport (cycle 15+ if there's demand)
- Globus / GridFTP integration (orthogonal — Globus has its own daemon)
- Encrypted credential cache (explicit non-goal — credential is meant
  to be ephemeral)
```

- [ ] **Step 2: Commit**

```bash
git add docs/architecture/ssh-broker.md
git commit -m "cycle-14 task 21: architecture doc — protocol, lifecycle, threat model"
```

---

## Task 22: Verify nothing regressed in cycle-12/13 SSH suite

**Files:** none (verification-only)

- [ ] **Step 1: Run the existing SSH unit tests**

```
uv run pytest tests/mcp/netcdf_reader/unit/test_ssh_silent_auth.py tests/mcp/netcdf_reader/unit/test_ssh_explicit_auth.py tests/mcp/netcdf_reader/unit/test_ssh_pool.py tests/mcp/netcdf_reader/unit/test_ssh_sftp_open.py tests/mcp/netcdf_reader/unit/test_ssh_inspect.py tests/mcp/netcdf_reader/unit/test_ssh_config.py -v
```
Expected: all passed. If any fails, the broker integration accidentally regressed the cycle-12 path — fix and re-commit before continuing.

- [ ] **Step 2: Run the existing classify tests**

```
uv run pytest tests/mcp/netcdf_reader/unit/test_classify.py -v
```
Expected: all passed.

- [ ] **Step 3: Run the existing adapter tests**

```
uv run pytest tests/mcp/netcdf_reader/unit/test_adapter.py tests/mcp/netcdf_reader/unit/test_adapter_decode_fallback.py -v
```
Expected: all passed.

- [ ] **Step 4: Run the bundle smoke**

```
uv run pytest tests/targets/claude_code/test_mcp_smoke.py -v
```
Expected: all passed.

If steps 1-4 all pass, no commit needed. If a fix is required, commit it as `cycle-14 task 22: <what regressed and why>`.

---

## Task 23: Final gate — full pytest + ruff + mypy

**Files:** any fixes needed

- [ ] **Step 1: Full pytest run**

```
uv run pytest -ra
```
Expected: all green. If broker-integration tests don't actually exercise broker subprocess (only in-proc) and run quickly, full suite should finish in normal time. Investigate any failure.

- [ ] **Step 2: Ruff lint**

```
uv run ruff check src tests
```
Expected: 0 errors. Fix any introduced by cycle 14 (typical: unused imports, line length on long error messages).

- [ ] **Step 3: Mypy type check**

```
uv run mypy src tools tests
```
Expected: no new errors beyond the pre-existing yaml-stub baseline. Fix any new mypy errors introduced (typical: `Any` returns from `_call`, untyped `MagicMock` in tests — annotate or `# type: ignore[...]`).

- [ ] **Step 4: README capability row (if applicable)**

If the README's top-of-file capability matrix lists per-cycle features (look for "cycle X" rows), add one row mentioning the broker. If no such matrix exists, skip this step.

- [ ] **Step 5: Verify tool counts unchanged**

```
uv run pytest tests/mcp/netcdf_reader/unit/test_server.py tests/mcp/plot_renderer/unit/test_server_dispatch.py -v
```
Expected: netcdf-reader still reports 14 tools, plot-renderer still reports 4. Cycle 14 adds NO new MCP tools — the broker is infra.

- [ ] **Step 6: Final commit (if any cleanup was needed)**

```bash
git add -A  # only if there's anything new
git commit -m "cycle-14 task 23: final gate — lint + type cleanup + verify counts"
```

If there's nothing to commit at this stage, skip the commit — the gate is just a verification.

---

## Self-Review (run after writing, before handing off)

### 1. Spec coverage

Walking through `docs/specs/2026-05-12-cycle-14-ssh-broker.md` §1 success criteria:

| # | Criterion | Task |
|---|---|---|
| 1 | `metplot-ssh-broker` CLI as bundled entry-point | Tasks 7 + 11 |
| 2 | Passcode lives entirely in user's terminal | Task 7 (`_authenticate` reads via `getpass`, drops on return) |
| 3 | One SFTP channel per broker | Task 3 (`SFTPHolder` opens one; invariant in docstring) |
| 4 | JSON-RPC over UNIX socket, 6 methods, 0600 | Tasks 2 + 4 + 5 + 6 |
| 5 | Keepalive + idle-shutdown | Tasks 3 (keepalive) + 10 (idle-shutdown integration) |
| 6 | Connection-lost honest | Tasks 5 (dispatch) + 10 (integration test) |
| 7 | `BrokerSFTPClient` mimics paramiko subset | Task 12 |
| 8 | `open_ssh_with_broker_fallback` | Task 13 |
| 9 | `adapter.open()` uses the fallback | Task 14 |
| 10 | Cycle-12 SSH tests still pass | Task 22 (verification) |
| 11 | `paths/classify.py` learns SSH globs | Task 15 |
| 12 | `broker_required` envelope on missing broker | Task 15 + 16 |
| 13 | `src/skills/netcdf-remote/SKILL.md` | Task 18 |
| 14 | `src/skills/netcdf-inspect/SKILL.md` updated | Task 19 |
| 15 | README subsection | Task 20 |
| 16 | pytest + ruff + mypy green | Task 23 |
| 17 | Bundle smoke updated | Task 11 |

All 17 criteria mapped. Architecture doc (§3.5) covered by Task 21 (bonus).

### 2. Placeholder scan

Grep for forbidden phrases — none of these appear in the task bodies above:
- "TBD" / "TODO" / "implement later" / "fill in"
- "Add appropriate error handling" / "handle edge cases" (each error path is shown with concrete code)
- "Write tests for the above" — every task has the actual test code
- "Similar to Task N" — task 6 stands alone with full test code
- All file paths are absolute or repo-relative concrete paths
- All commands include the full `uv run pytest` invocation

### 3. Type consistency

- `make_request` / `make_response` / `make_error` named consistently across Task 2 and Tasks 5/12.
- `BrokerError.code` is `int`, used as `int` in `_dispatch_one` (Task 5) — consistent.
- `SFTPHolder.sftp` set in `__init__` (Task 3), accessed in `_dispatch_one` and integration tests — consistent.
- `BrokerSFTPClient.listdir_attr` returns `list[_LikeSFTPAttributes]` (Task 12) — has `.filename`, `.st_size`, `.st_mode`, `.st_mtime`. The MCP's existing callers of paramiko's `SFTPClient.listdir_attr` use exactly these fields (verified — no `st_atime` / `st_uid` etc. is read by inspect.py).
- `BrokerSFTPClient.glob_remote` named consistently across Task 12 (impl) and Task 15 (consumer).
- `discover_broker_socket` / `open_ssh_with_broker_fallback` named consistently across Tasks 13, 14, 15, 16.
- `PathKind.SSH_MULTI` introduced in Task 15, paths list shape (`ssh://...` URLs) matches what `adapter.open()` expects for multi-file paths (Task 14 currently handles single ssh path; **note for executor:** multi-file ssh paths are not exercised by any of these tests — the broker glob test stops at `classify()`. Multi-file open via broker is a natural extension but explicitly out of cycle-14 scope per the spec §2.).

No type drift detected.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-12-cycle-14-ssh-broker.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for a 23-task plan: the main context stays clean and each task is verified before moving on.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`. Batched execution with checkpoints for review. Best if you want to watch each task scroll by.

Which approach?
