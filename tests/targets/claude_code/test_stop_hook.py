# tests/targets/claude_code/test_stop_hook.py
"""Cycle-6 Phase B contract: a `Stop` hook fires `/metplot:refine` in
a fresh subagent at the end of every Claude Code session.

Real hook firing is out of scope for CI (cycle-6 spec §1 "Real Stop
hook firing in CI — out of scope … manual verification during the
post-build dogfood follow-up"). This file asserts the config shape
only: hook is registered, has the right event type, matcher, and
command, and the command never blocks the parent session end.

Per spec §3.3 (cycle-6 self-improvement-loop)."""
from __future__ import annotations

import json
from pathlib import Path


def test_refine_hook_file_present(built_plugin: Path) -> None:
    assert (built_plugin / "hooks" / "refine.json").is_file(), (
        "Stop hook config must ship as hooks/refine.json")


def test_refine_hook_parses_as_json(built_plugin: Path) -> None:
    text = (built_plugin / "hooks" / "refine.json").read_text()
    json.loads(text)


def test_refine_hook_registers_stop_event(built_plugin: Path) -> None:
    """Hook must register against Claude Code's `Stop` event so it
    fires at session end, not SessionStart or some other event."""
    cfg = json.loads(
        (built_plugin / "hooks" / "refine.json").read_text())
    assert "Stop" in cfg, (
        f"refine hook must register against 'Stop'; got keys {list(cfg)}")
    assert isinstance(cfg["Stop"], list) and len(cfg["Stop"]) >= 1


def test_refine_hook_has_wildcard_matcher(built_plugin: Path) -> None:
    """Run on every session-end, not a subset — refinement should
    happen any time there's signal in the task log."""
    cfg = json.loads(
        (built_plugin / "hooks" / "refine.json").read_text())
    entry = cfg["Stop"][0]
    assert entry.get("matcher") == "*", (
        f"refine hook matcher must be '*'; got {entry.get('matcher')!r}")


def test_refine_hook_invokes_refine_slash_command(
    built_plugin: Path,
) -> None:
    """The hook's command line must invoke /metplot:refine — the
    whole point of the Stop hook is to route the agent at the
    refiner skill."""
    cfg = json.loads(
        (built_plugin / "hooks" / "refine.json").read_text())
    entry = cfg["Stop"][0]
    hooks = entry.get("hooks", [])
    assert hooks and any(
        "/metplot:refine" in h.get("command", "") for h in hooks
    ), (
        f"no hook in refine.json invokes /metplot:refine; "
        f"hooks: {hooks!r}")


def test_refine_hook_command_is_type_command(built_plugin: Path) -> None:
    """Claude Code's hook schema requires type='command' for shell
    invocations. Anything else (script, ...) would silently no-op."""
    cfg = json.loads(
        (built_plugin / "hooks" / "refine.json").read_text())
    for h in cfg["Stop"][0]["hooks"]:
        assert h.get("type") == "command", (
            f"hook entry must be type='command'; got {h!r}")


def test_refine_hook_exits_zero_always(built_plugin: Path) -> None:
    """Spec §4 principle 6: 'Stop hook = fresh subagent, exit-0
    always. … never break the host's session-end flow.' The command
    must terminate with a literal exit-0 even when sub-invocations
    fail (e.g. `claude` not on PATH)."""
    cfg = json.loads(
        (built_plugin / "hooks" / "refine.json").read_text())
    for h in cfg["Stop"][0]["hooks"]:
        cmd = h.get("command", "")
        assert "exit 0" in cmd, (
            f"hook command must defensively `exit 0`; got: {cmd!r}")


def test_refine_hook_does_not_block_parent_session(
    built_plugin: Path,
) -> None:
    """Spec §4.6 forbids the refiner from blocking session end. The
    subagent invocation must therefore be backgrounded — looking
    for the shell job-control `&` operator in the command."""
    cfg = json.loads(
        (built_plugin / "hooks" / "refine.json").read_text())
    for h in cfg["Stop"][0]["hooks"]:
        cmd = h.get("command", "")
        if "/metplot:refine" in cmd:
            assert "&" in cmd, (
                f"refine subagent must be backgrounded so the Stop hook "
                f"returns immediately; got: {cmd!r}")


def test_refine_hook_guards_against_missing_claude_binary(
    built_plugin: Path,
) -> None:
    """The hook ships in builds where the user may not have the
    `claude` CLI on PATH (e.g. plugin installed but Claude Code
    invoked via a different binary name). Guarding against missing
    `claude` keeps the hook from spamming the user with shell errors
    at session end. Looking for `command -v claude` or `which
    claude` as the defensive check."""
    cfg = json.loads(
        (built_plugin / "hooks" / "refine.json").read_text())
    for h in cfg["Stop"][0]["hooks"]:
        cmd = h.get("command", "")
        if "/metplot:refine" in cmd:
            assert ("command -v claude" in cmd
                    or "which claude" in cmd), (
                f"refine hook must guard against missing `claude` "
                f"binary; got: {cmd!r}")
