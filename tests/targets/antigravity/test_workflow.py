from pathlib import Path

def test_refine_workflow_present(built_plugin: Path):
    assert (built_plugin / ".agent" / "workflows" / "refine.md").is_file()

def test_refine_has_frontmatter(built_plugin: Path):
    text = (built_plugin / ".agent" / "workflows" / "refine.md").read_text()
    assert text.startswith("---\n")

def test_refine_announces_placeholder(built_plugin: Path):
    text = (built_plugin / ".agent" / "workflows" / "refine.md").read_text()
    assert "placeholder" in text.lower() or "cycle 6" in text.lower()


def test_setup_workflow_present(built_plugin: Path):
    assert (built_plugin / ".agent" / "workflows" / "setup.md").is_file()


def test_setup_workflow_has_frontmatter(built_plugin: Path):
    text = (built_plugin / ".agent" / "workflows" / "setup.md").read_text()
    assert text.startswith("---\n")


def test_setup_workflow_mentions_setup_sh(built_plugin: Path):
    text = (built_plugin / ".agent" / "workflows" / "setup.md").read_text()
    assert "setup.sh" in text
