"""metplot-ssh-broker CLI argument parsing and socket-path resolution.

main() itself is not tested here — it does interactive auth and
spawns a server thread, which is integration territory.
"""
from __future__ import annotations

import pytest

from src.ssh_broker.cli import (
    _split_user_host,
    build_parser,
    default_socket_path,
    resolve_user_and_host,
)


def test_parser_accepts_host_positional():
    p = build_parser()
    ns = p.parse_args(["home.ccs.ornl.gov"])
    assert ns.host == "home.ccs.ornl.gov"
    assert ns.port == 22
    assert ns.user is None
    assert ns.idle_timeout == 7200.0
    assert ns.keepalive == 30
    assert ns.allow_exec is None or ns.allow_exec == ""


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


def test_parser_accepts_idle_timeout_float():
    p = build_parser()
    ns = p.parse_args(["--idle-timeout", "1800", "h"])
    assert ns.idle_timeout == 1800.0


def test_parser_accepts_keepalive():
    p = build_parser()
    ns = p.parse_args(["--keepalive", "60", "h"])
    assert ns.keepalive == 60


def test_parser_accepts_allow_exec():
    p = build_parser()
    ns = p.parse_args(["--allow-exec", "ncks,find", "h"])
    assert ns.allow_exec == "ncks,find"


def test_default_socket_path_uses_xdg_runtime_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    p = default_socket_path("home.ccs.ornl.gov", socket_dir=None)
    assert p == str(tmp_path / "metplot-ssh" / "home.ccs.ornl.gov.sock")


def test_default_socket_path_falls_back_to_tmp(monkeypatch):
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


def test_split_user_host_no_prefix():
    assert _split_user_host("home.example", None) == ("home.example", None)


def test_split_user_host_prefix_without_explicit_user():
    assert _split_user_host("alice@home.example", None) == ("home.example", "alice")


def test_split_user_host_explicit_user_overrides_prefix_silently(capsys):
    result = _split_user_host("alice@home.example", "bob")
    assert result == ("home.example", "bob")
    captured = capsys.readouterr()
    assert captured.err == ""  # no warning
    assert captured.out == ""


def test_split_user_host_multiple_at_signs_split_on_first():
    assert _split_user_host("a@b@c.example", None) == ("b@c.example", "a")


def test_split_user_host_empty_username_rejected(capsys):
    with pytest.raises(SystemExit) as excinfo:
        _split_user_host("@home.example", None)
    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "empty username before '@'" in captured.err


def test_split_user_host_empty_host_rejected(capsys):
    with pytest.raises(SystemExit) as excinfo:
        _split_user_host("alice@", None)
    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "empty host after '@'" in captured.err


def test_resolve_user_and_host_falls_back_to_USER(monkeypatch):
    monkeypatch.setenv("USER", "carol")
    p = build_parser()
    ns = p.parse_args(["home.example"])
    host, user = resolve_user_and_host(ns)
    assert host == "home.example"
    assert user == "carol"
