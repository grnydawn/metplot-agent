"""Read-only-exec policy for the metplot-ssh-broker.

The broker exposes a generic `exec(argv, timeout)` JSON-RPC method
but constrains it to a hardcoded read-only tool allowlist. This
module:

  1. Defines BUILTIN_ALLOWLIST — tools that are read-only-by-design
     when given a single path argument. Adding to this set is a
     deliberate spec change, not a config option.

  2. Provides is_allowed(tool, extra_allowed) — the gate the broker
     calls before opening an exec channel. extra_allowed comes from
     the user's --allow-exec CLI flag.

  3. Provides quote_argv(argv) — shlex-quotes each argv element
     before joining for paramiko.transport.exec_command(). This
     blocks shell-metacharacter injection: a user-supplied
     argv=['ls', '>foo'] becomes "ls '>foo'", which the shell treats
     as a single literal argument to ls (no redirection).
"""
from __future__ import annotations

import shlex
from typing import Iterable

# Locked-in. Read-only tools that take a single path. Adding to
# this set is a deliberate spec change (see
# docs/specs/2026-05-12-cycle-14-ssh-broker.md §1.4).
BUILTIN_ALLOWLIST: frozenset[str] = frozenset({
    "ncdump", "ls", "cat", "head", "tail", "wc", "file", "stat",
})


class ToolNotInAllowlist(Exception):
    """Raised when exec() is called with a tool not in the allowlist."""

    def __init__(self, tool: str) -> None:
        super().__init__(f"tool not in exec allowlist: {tool}")
        self.tool = tool


def is_allowed(tool: str, extra_allowed: Iterable[str] | None = None
               ) -> bool:
    """Return True iff `tool` is permitted by the broker's policy.

    `extra_allowed` is the user's --allow-exec set (or None / empty).
    The decision: tool ∈ BUILTIN_ALLOWLIST ∪ extra_allowed.
    """
    if tool in BUILTIN_ALLOWLIST:
        return True
    if extra_allowed is not None and tool in set(extra_allowed):
        return True
    return False


def quote_argv(argv: list[str]) -> str:
    """Shlex-quote each element of `argv` and join with spaces.

    The result is safe to pass to a shell (which paramiko's
    transport.exec_command effectively does via the remote sshd's
    user shell). Metacharacters in user-supplied argv elements are
    quoted, not interpreted.
    """
    if not argv:
        raise ValueError("argv must be non-empty")
    return " ".join(shlex.quote(a) for a in argv)
