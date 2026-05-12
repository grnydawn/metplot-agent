# tests/targets/gemini_cli/test_commands.py
# Cycle-5: refine.toml moved into commands/metplot/ subdir (namespace pattern).
from pathlib import Path
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def test_refine_toml_present(built_plugin: Path):
    assert (built_plugin / "commands" / "metplot" / "refine.toml").is_file()


def test_refine_toml_not_at_top_level(built_plugin: Path):
    assert not (built_plugin / "commands" / "refine.toml").exists()


def test_refine_toml_parses(built_plugin: Path):
    d = tomllib.loads((built_plugin / "commands" / "metplot" / "refine.toml").read_text())
    assert "description" in d
    assert "prompt" in d


def test_refine_no_placeholder_or_cycle_tokens(built_plugin: Path):
    """Cycle-6 Phase B shipped skill-refiner — the refine body must
    no longer call itself a placeholder or reference cycle 6."""
    text = (built_plugin / "commands" / "metplot" / "refine.toml").read_text().lower()
    for tok in ("placeholder", "cycle 6", "until cycle", "will be"):
        assert tok not in text, f"deferral token leaked: {tok!r}"


def test_refine_invokes_skill_refiner(built_plugin: Path):
    text = (built_plugin / "commands" / "metplot" / "refine.toml").read_text()
    assert "skill-refiner" in text.lower()
    assert ".metplot/task-log.jsonl" in text
    assert ".metplot/refinements/" in text


def test_refine_calls_out_manual_trigger(built_plugin: Path):
    """Gemini CLI has no Stop-hook equivalent; the body must flag
    this so the user knows refinement won't auto-fire."""
    text = (built_plugin / "commands" / "metplot" / "refine.toml").read_text().lower()
    assert "manual" in text or "no stop-hook" in text or "no stop hook" in text


def test_setup_toml_in_metplot_subdir(built_plugin: Path):
    assert (built_plugin / "commands" / "metplot" / "setup.toml").is_file()


def test_refine_moved_to_metplot_subdir(built_plugin: Path):
    assert (built_plugin / "commands" / "metplot" / "refine.toml").is_file()
    assert not (built_plugin / "commands" / "refine.toml").exists()
