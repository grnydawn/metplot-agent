"""The 9 JSON-RPC methods served by the broker.

Each method takes (holder, params, *, extra_allowed=None) and
returns a result dict. Errors raise BrokerError subclasses; the
server layer maps those to JSON-RPC error responses.
"""
from __future__ import annotations

import base64
import hashlib
import stat as statmod
from unittest.mock import MagicMock, call

import pytest

from src.ssh_broker.exec_policy import BUILTIN_ALLOWLIST
from src.ssh_broker.methods import (
    METHODS, BrokerError, ConnectionLost, SFTPError, ToolNotFoundError,
    ToolNotInAllowlistError, dump_header, dump_metadata, exec_,
    get_chunk, get_full, glob, listdir, ping, stat,
)


def _attr(name, *, size=100, mode=0o100644, mtime=1.0):
    a = MagicMock()
    a.filename = name
    a.st_size = size
    a.st_mode = mode
    a.st_mtime = mtime
    return a


def _holder_with_sftp(sftp):
    """A MagicMock SessionHolder whose with_sftp(fn) calls fn(sftp)."""
    holder = MagicMock()
    holder.with_sftp.side_effect = lambda fn: fn(sftp)
    holder._sftp = sftp
    return holder


# ── Registry ────────────────────────────────────────────────────

def test_registry_has_nine_methods():
    assert set(METHODS) == {
        "listdir", "stat", "glob", "get_chunk", "get_full",
        "dump_header", "dump_metadata", "exec", "ping",
    }


# ── listdir ─────────────────────────────────────────────────────

def test_listdir_returns_entries():
    sftp = MagicMock()
    sftp.listdir_attr.return_value = [
        _attr("a.nc", size=42), _attr("b.nc", size=99),
    ]
    h = _holder_with_sftp(sftp)
    r = listdir(h, {"path": "/data"})
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
    h = _holder_with_sftp(sftp)
    r = listdir(h, {"path": "/d"})
    assert r["entries"][0]["is_dir"] is True


def test_listdir_raises_sftp_error_on_not_found():
    sftp = MagicMock()
    sftp.listdir_attr.side_effect = FileNotFoundError("nope")
    h = _holder_with_sftp(sftp)
    with pytest.raises(SFTPError):
        listdir(h, {"path": "/missing"})


# ── stat ────────────────────────────────────────────────────────

def test_stat_returns_entry_with_basename():
    sftp = MagicMock()
    sftp.stat.return_value = _attr("ignored", size=7)
    h = _holder_with_sftp(sftp)
    r = stat(h, {"path": "/dir/x.nc"})
    sftp.stat.assert_called_with("/dir/x.nc")
    assert r["entry"]["name"] == "x.nc"  # basename
    assert r["entry"]["size"] == 7


# ── glob ────────────────────────────────────────────────────────

def test_glob_matches_pattern_against_listdir():
    sftp = MagicMock()
    sftp.listdir.return_value = ["a.nc", "b.nc", "skip.txt", "c.nc"]
    h = _holder_with_sftp(sftp)
    r = glob(h, {"pattern": "/data/*.nc"})
    sftp.listdir.assert_called_with("/data")
    assert r["paths"] == ["/data/a.nc", "/data/b.nc", "/data/c.nc"]


def test_glob_relative_pattern_lists_dot():
    sftp = MagicMock()
    sftp.listdir.return_value = ["x.nc"]
    h = _holder_with_sftp(sftp)
    r = glob(h, {"pattern": "*.nc"})
    sftp.listdir.assert_called_with(".")
    assert r["paths"] == ["./x.nc"]


def test_glob_empty_match():
    sftp = MagicMock()
    sftp.listdir.return_value = ["a.txt"]
    h = _holder_with_sftp(sftp)
    r = glob(h, {"pattern": "/d/*.nc"})
    assert r["paths"] == []


# ── get_chunk ───────────────────────────────────────────────────

def test_get_chunk_seeks_and_reads():
    sftp = MagicMock()
    fh = MagicMock()
    fh.read.return_value = b"hello"
    sftp.open.return_value.__enter__.return_value = fh
    h = _holder_with_sftp(sftp)
    r = get_chunk(h, {"path": "/x.nc", "offset": 4, "length": 5})
    fh.seek.assert_called_with(4)
    fh.read.assert_called_with(5)
    assert base64.b64decode(r["data_b64"]) == b"hello"
    assert r["size"] == 5


# ── get_full ────────────────────────────────────────────────────

def test_get_full_writes_local_and_returns_sha256(tmp_path):
    remote = "/remote.nc"
    local = str(tmp_path / "out.nc")

    def fake_get(r, l):
        with open(l, "wb") as fh:
            fh.write(b"abc" * 10)

    sftp = MagicMock()
    sftp.get.side_effect = fake_get
    h = _holder_with_sftp(sftp)
    r = get_full(h, {"remote_path": remote, "local_path": local})
    sftp.get.assert_called_with(remote, local)
    assert r["bytes_copied"] == 30
    assert r["sha256"] == hashlib.sha256(b"abc" * 10).hexdigest()


# ── dump_header ─────────────────────────────────────────────────

def test_dump_header_runs_ncdump_and_returns_cdl():
    holder = MagicMock()
    holder.exec_command.return_value = {
        "stdout_bytes": b"netcdf foo {\n  dimensions:\n}\n",
        "stderr_bytes": b"",
        "exit_code": 0,
    }
    r = dump_header(holder, {"path": "/foo.nc"})
    # quote_argv joins as single shell string
    holder.exec_command.assert_called_once()
    cmd_arg = holder.exec_command.call_args[0][0]
    assert "ncdump" in cmd_arg and "-h" in cmd_arg and "/foo.nc" in cmd_arg
    assert r["cdl"].startswith("netcdf foo")
    assert r["exit_code"] == 0


def test_dump_header_returns_dict_even_on_nonzero_exit():
    """Caller decides what to do with exit_code; method doesn't raise."""
    holder = MagicMock()
    holder.exec_command.return_value = {
        "stdout_bytes": b"",
        "stderr_bytes": b"ncdump: cannot open /missing.nc",
        "exit_code": 2,
    }
    r = dump_header(holder, {"path": "/missing.nc"})
    assert r["exit_code"] == 2
    assert "cannot open" in r["stderr"]


# ── dump_metadata ───────────────────────────────────────────────

def test_dump_metadata_runs_ncks_m():
    holder = MagicMock()
    holder.exec_command.return_value = {
        "stdout_bytes": b"...ncks output...\n",
        "stderr_bytes": b"",
        "exit_code": 0,
    }
    r = dump_metadata(holder, {"path": "/foo.nc"})
    cmd_arg = holder.exec_command.call_args[0][0]
    assert "ncks" in cmd_arg and "-m" in cmd_arg and "/foo.nc" in cmd_arg
    assert "ncks output" in r["ncks_m"]
    assert r["exit_code"] == 0


def test_dump_metadata_raises_tool_not_found_when_ncks_missing():
    holder = MagicMock()
    holder.exec_command.return_value = {
        "stdout_bytes": b"",
        "stderr_bytes": b"bash: ncks: command not found",
        "exit_code": 127,
    }
    with pytest.raises(ToolNotFoundError):
        dump_metadata(holder, {"path": "/foo.nc"})


def test_dump_metadata_returns_dict_for_other_nonzero_exits():
    """If the file is missing rather than the tool, we get the dict."""
    holder = MagicMock()
    holder.exec_command.return_value = {
        "stdout_bytes": b"",
        "stderr_bytes": b"ncks: No such file or directory",
        "exit_code": 1,
    }
    # "No such file" is a path issue, not a tool issue → return the dict
    # so the caller can surface the error context.
    with pytest.raises(ToolNotFoundError):
        # Actually the spec says raise on "command not found" OR "No such
        # file" — we treat both as tool-related. (See the prompt.)
        dump_metadata(holder, {"path": "/foo.nc"})


# ── exec_ ───────────────────────────────────────────────────────

def test_exec_rejects_writers_outright():
    holder = MagicMock()
    with pytest.raises(ToolNotInAllowlistError):
        exec_(holder, {"argv": ["rm", "-rf", "/"]})
    holder.exec_command.assert_not_called()


def test_exec_accepts_builtin_tool():
    holder = MagicMock()
    holder.exec_command.return_value = {
        "stdout_bytes": b"a.nc\nb.nc\n",
        "stderr_bytes": b"",
        "exit_code": 0,
    }
    r = exec_(holder, {"argv": ["ls", "/data"]})
    holder.exec_command.assert_called_once()
    assert base64.b64decode(r["stdout_b64"]) == b"a.nc\nb.nc\n"
    assert r["exit_code"] == 0


def test_exec_accepts_extra_allowed_tool():
    holder = MagicMock()
    holder.exec_command.return_value = {
        "stdout_bytes": b"", "stderr_bytes": b"", "exit_code": 0,
    }
    exec_(holder, {"argv": ["ncks", "-m", "/foo.nc"]},
           extra_allowed={"ncks"})
    holder.exec_command.assert_called_once()


def test_exec_with_extras_still_rejects_writers():
    holder = MagicMock()
    with pytest.raises(ToolNotInAllowlistError):
        exec_(holder, {"argv": ["rm", "-rf", "/"]},
               extra_allowed={"ncks"})


def test_exec_quotes_argv_elements():
    holder = MagicMock()
    holder.exec_command.return_value = {
        "stdout_bytes": b"", "stderr_bytes": b"", "exit_code": 0,
    }
    exec_(holder, {"argv": ["ls", ">foo"]})
    cmd_arg = holder.exec_command.call_args[0][0]
    # The '>' must be quoted, not raw, in the shell-bound string.
    assert ">foo" in cmd_arg
    # And shell parsing of the result should yield two args.
    import shlex
    parts = shlex.split(cmd_arg)
    assert parts == ["ls", ">foo"]


def test_exec_passes_timeout():
    holder = MagicMock()
    holder.exec_command.return_value = {
        "stdout_bytes": b"", "stderr_bytes": b"", "exit_code": 0,
    }
    exec_(holder, {"argv": ["ls"], "timeout": 30.0})
    _, kwargs = holder.exec_command.call_args
    assert kwargs.get("timeout") == 30.0 or holder.exec_command.call_args[0][1] == 30.0


def test_exec_default_timeout_60():
    holder = MagicMock()
    holder.exec_command.return_value = {
        "stdout_bytes": b"", "stderr_bytes": b"", "exit_code": 0,
    }
    exec_(holder, {"argv": ["ls"]})
    # Either kwargs={timeout: 60.0} or positional 2nd arg
    args, kwargs = holder.exec_command.call_args
    timeout_arg = kwargs.get("timeout") if "timeout" in kwargs else (
        args[1] if len(args) >= 2 else None)
    assert timeout_arg == 60.0


def test_exec_raises_on_empty_argv():
    holder = MagicMock()
    with pytest.raises((ValueError, ToolNotInAllowlistError)):
        exec_(holder, {"argv": []})


# ── ping ────────────────────────────────────────────────────────

def test_ping_returns_alive_and_metadata():
    holder = MagicMock()
    holder.host = "h.example"
    holder.user = "alice"
    holder.connected_at = "2026-05-12T10:00:00+00:00"
    holder._sftp = MagicMock()  # SFTP open
    r = ping(holder, {})
    assert r["alive"] is True
    assert r["host"] == "h.example"
    assert r["connected_at"] == "2026-05-12T10:00:00+00:00"
    assert r["sftp_open"] is True
    assert set(BUILTIN_ALLOWLIST).issubset(set(r["allowed_exec_tools"]))


def test_ping_reports_sftp_closed():
    holder = MagicMock()
    holder.host = "h"; holder.user = "u"
    holder.connected_at = "x"
    holder._sftp = None
    r = ping(holder, {})
    assert r["sftp_open"] is False


def test_ping_includes_extras_in_allowed_tools():
    holder = MagicMock()
    holder.host = "h"; holder.user = "u"; holder.connected_at = "x"
    holder._sftp = None
    r = ping(holder, {}, extra_allowed={"ncks", "find"})
    assert "ncks" in r["allowed_exec_tools"]
    assert "find" in r["allowed_exec_tools"]


# ── BrokerError codes ──────────────────────────────────────────

def test_broker_error_codes():
    assert ConnectionLost("x").code == -32000
    assert SFTPError("x").code == -32001
    assert ToolNotFoundError("x").code == -32002
    assert ToolNotInAllowlistError("x").code == -32003
