from pathlib import Path


def test_refine_md_present(built_plugin: Path):
    assert (built_plugin / "commands" / "refine.md").is_file()


def test_refine_has_frontmatter(built_plugin: Path):
    text = (built_plugin / "commands" / "refine.md").read_text()
    assert text.startswith("---\n")


def test_refine_no_placeholder_or_cycle_tokens(built_plugin: Path):
    """Cycle-6 Phase B shipped skill-refiner — the refine body must
    no longer call itself a placeholder or reference cycle 6."""
    text = (built_plugin / "commands" / "refine.md").read_text().lower()
    for tok in ("placeholder", "cycle 6", "until cycle", "will be"):
        assert tok not in text, f"deferral token leaked: {tok!r}"


def test_refine_invokes_skill_refiner(built_plugin: Path):
    """The body must route the agent at the skill."""
    text = (built_plugin / "commands" / "refine.md").read_text()
    assert "skill-refiner" in text.lower()
    assert ".metplot/task-log.jsonl" in text
    assert ".metplot/refinements/" in text


def test_refine_calls_out_manual_trigger(built_plugin: Path):
    """Cursor has no Stop hook; the body must say this explicitly so
    the user knows refinement won't fire automatically here."""
    text = (built_plugin / "commands" / "refine.md").read_text().lower()
    assert "manual" in text or "no stop-hook" in text or "no stop hook" in text


def test_setup_command_present(built_plugin: Path):
    assert (built_plugin / "commands" / "setup.md").is_file()


def test_setup_command_has_frontmatter(built_plugin: Path):
    text = (built_plugin / "commands" / "setup.md").read_text()
    assert text.startswith("---\n")
