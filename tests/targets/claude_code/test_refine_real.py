# tests/targets/claude_code/test_refine_real.py
"""Cycle-6 Phase B contract: /refine is the real shipped command,
not a placeholder. Asserts on the body content rather than just the
file's existence (that's in test_commands_dir.py).

Per spec §3.3 (cycle-6 self-improvement-loop)."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def refine_md_text(built_plugin: Path) -> str:
    return (built_plugin / "commands" / "refine.md").read_text()


def test_no_placeholder_token(refine_md_text: str) -> None:
    """No 'placeholder' anywhere — case-insensitive, full-text scan."""
    assert "placeholder" not in refine_md_text.lower(), (
        "/refine body still calls itself a placeholder; Phase B shipped "
        "the real implementation")


def test_no_cycle_deferral_tokens(refine_md_text: str) -> None:
    """No 'cycle 6' / 'cycle six' deferral language — and no generic
    'cycle N' references either, since the shipped body shouldn't
    leak development planning into the user-facing surface."""
    lower = refine_md_text.lower()
    for tok in ("cycle 6", "cycle six",
                "lands in cycle", "will be", "coming soon",
                "once that's implemented", "until cycle"):
        assert tok not in lower, f"deferral token leaked into refine.md: {tok!r}"


def test_invokes_skill_refiner_skill(refine_md_text: str) -> None:
    """The whole point of the command is to route the agent at the
    skill. Be lax on phrasing — case-insensitive contains."""
    assert "skill-refiner" in refine_md_text.lower(), (
        "/refine body must reference the skill-refiner skill by name")


def test_names_task_log_input(refine_md_text: str) -> None:
    """Refiner reads the task log — must be cited in the body so the
    agent knows where to look."""
    assert ".metplot/task-log.jsonl" in refine_md_text


def test_names_refinements_output_dir(refine_md_text: str) -> None:
    """Drafts go to .metplot/refinements/, not direct edits."""
    assert ".metplot/refinements/" in refine_md_text


def test_calls_out_human_review_boundary(refine_md_text: str) -> None:
    """Per spec §4 principle 6, the body must encode the
    drafts-not-direct-edits contract user-side. Looser check — any
    mention that this is review-mediated."""
    lower = refine_md_text.lower()
    review_signals = (
        "do not modify",
        "human review",
        "human-review",
        "for review",
        "user reviews",
        "metplot-refine",
    )
    assert any(s in lower for s in review_signals), (
        f"/refine body must signal the human-review boundary; "
        f"none of {review_signals!r} found")


def test_body_is_short_and_procedural(refine_md_text: str) -> None:
    """Spec §4 principle 8 caps slash-command bodies at ~5–10 lines of
    procedural content (excluding frontmatter and blank lines). Keep
    them tight."""
    # Strip frontmatter.
    parts = refine_md_text.split("---\n", 2)
    assert len(parts) >= 3, "frontmatter not properly terminated"
    body = parts[2]
    # Count non-blank lines as the procedural-content metric.
    content_lines = [ln for ln in body.splitlines() if ln.strip()]
    assert len(content_lines) <= 12, (
        f"/refine body has {len(content_lines)} non-blank lines; "
        f"spec §4.8 caps at ~10. Body:\n{body}")
