from pathlib import Path

def test_refine_workflow_present(built_plugin: Path):
    assert (built_plugin / ".agent" / "workflows" / "refine.md").is_file()

def test_refine_has_frontmatter(built_plugin: Path):
    text = (built_plugin / ".agent" / "workflows" / "refine.md").read_text()
    assert text.startswith("---\n")

def test_refine_no_placeholder_or_cycle_tokens(built_plugin: Path):
    """Cycle-6 Phase B shipped skill-refiner — the refine body must
    no longer call itself a placeholder or reference cycle 6."""
    text = (built_plugin / ".agent" / "workflows" / "refine.md").read_text().lower()
    for tok in ("placeholder", "cycle 6", "until cycle", "will be"):
        assert tok not in text, f"deferral token leaked: {tok!r}"


def test_refine_invokes_skill_refiner(built_plugin: Path):
    text = (built_plugin / ".agent" / "workflows" / "refine.md").read_text()
    assert "skill-refiner" in text.lower()
    assert ".metplot/task-log.jsonl" in text
    assert ".metplot/refinements/" in text


def test_refine_calls_out_manual_trigger(built_plugin: Path):
    """Antigravity has no formal hook system; the body must flag
    that this workflow is manual-only on this host."""
    text = (built_plugin / ".agent" / "workflows" / "refine.md").read_text().lower()
    assert "manual" in text or "no hook" in text or "no formal hook" in text


def test_setup_workflow_present(built_plugin: Path):
    assert (built_plugin / ".agent" / "workflows" / "setup.md").is_file()


def test_setup_workflow_has_frontmatter(built_plugin: Path):
    text = (built_plugin / ".agent" / "workflows" / "setup.md").read_text()
    assert text.startswith("---\n")


def test_setup_workflow_mentions_setup_sh(built_plugin: Path):
    text = (built_plugin / ".agent" / "workflows" / "setup.md").read_text()
    assert "setup.sh" in text
