"""exec_policy — read-only allowlist + shlex-quoted argv joining.

The broker rejects any exec(argv) whose argv[0] isn't in the
built-in allowlist OR the extra-allowed list passed at broker
startup. Built-in is read-only-by-design tools that take a single
path argument; extras are user-accepted-responsibility.

quote_argv defends against shell-metacharacter injection through
user-supplied argv elements by shlex-quoting each before joining.
"""
from __future__ import annotations

import pytest

from src.ssh_broker.exec_policy import (
    BUILTIN_ALLOWLIST, ToolNotInAllowlist, is_allowed, quote_argv,
)


# ── Allowlist content ──────────────────────────────────────────

def test_builtin_allowlist_is_a_frozenset():
    """Immutable so a runtime caller can't grow it accidentally."""
    assert isinstance(BUILTIN_ALLOWLIST, frozenset)


def test_builtin_allowlist_contents():
    """Locked-in set — adding tools is a deliberate spec change."""
    assert BUILTIN_ALLOWLIST == frozenset({
        "ncdump", "ls", "cat", "head", "tail", "wc", "file", "stat",
    })


# ── is_allowed ─────────────────────────────────────────────────

def test_is_allowed_accepts_builtin():
    assert is_allowed("ncdump") is True
    assert is_allowed("ls") is True


def test_is_allowed_rejects_writers_outright():
    # Even with no extras specified, these are explicitly NOT in
    # the built-in list and must be rejected.
    for writer in ("rm", "mv", "cp", "mkdir", "chmod", "chown",
                    "dd", "tee", "touch", "ln", "rmdir"):
        assert is_allowed(writer) is False, f"{writer!r} should be rejected"


def test_is_allowed_rejects_shells_and_meta_runners():
    for s in ("sh", "bash", "zsh", "fish", "python", "perl",
              "eval", "exec"):
        assert is_allowed(s) is False, f"{s!r} should be rejected"


def test_is_allowed_accepts_extras():
    assert is_allowed("ncks", extra_allowed={"ncks"}) is True
    assert is_allowed("find", extra_allowed={"ncks", "find"}) is True


def test_is_allowed_with_extras_still_rejects_writers():
    # User explicitly added ncks (read-only flag wrap-around).
    # rm is NOT in extras → still rejected.
    assert is_allowed("rm", extra_allowed={"ncks"}) is False


def test_is_allowed_empty_extras_falls_back_to_builtin():
    assert is_allowed("ncdump", extra_allowed=set()) is True
    assert is_allowed("ncdump", extra_allowed=None) is True


# ── quote_argv ─────────────────────────────────────────────────

def test_quote_argv_joins_simple_argv():
    assert quote_argv(["ls", "/data"]) == "ls /data"


def test_quote_argv_blocks_redirection_injection():
    """argv=['ls', '>foo'] must NOT cause shell redirection — the
    '>foo' must be passed literally to ls."""
    result = quote_argv(["ls", ">foo"])
    # The exact form depends on shlex.quote's choices, but it MUST
    # be quoted somehow such that the shell sees it as a single arg.
    # Most reliable check: round-trip via shlex.split and verify.
    import shlex
    assert shlex.split(result) == ["ls", ">foo"]


def test_quote_argv_blocks_pipe_injection():
    result = quote_argv(["cat", "a.txt | rm -rf /"])
    import shlex
    assert shlex.split(result) == ["cat", "a.txt | rm -rf /"]


def test_quote_argv_blocks_command_substitution():
    result = quote_argv(["echo", "$(whoami)"])
    import shlex
    assert shlex.split(result) == ["echo", "$(whoami)"]


def test_quote_argv_blocks_semicolon_chain():
    result = quote_argv(["ls", "; rm -rf /"])
    import shlex
    assert shlex.split(result) == ["ls", "; rm -rf /"]


def test_quote_argv_blocks_backtick():
    result = quote_argv(["echo", "`id`"])
    import shlex
    assert shlex.split(result) == ["echo", "`id`"]


def test_quote_argv_handles_empty_strings():
    """Edge: shlex must produce a parseable quoted empty string."""
    result = quote_argv(["wc", ""])
    import shlex
    assert shlex.split(result) == ["wc", ""]


def test_quote_argv_handles_single_element():
    assert quote_argv(["ncdump"]) == "ncdump"


def test_quote_argv_raises_on_empty_argv():
    with pytest.raises(ValueError):
        quote_argv([])


# ── ToolNotInAllowlist exception ───────────────────────────────

def test_tool_not_in_allowlist_carries_the_tool_name():
    e = ToolNotInAllowlist("rm")
    assert e.tool == "rm"
    assert "rm" in str(e)
