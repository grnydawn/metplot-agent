from pathlib import Path


def test_setup_command_present(built_plugin: Path):
    assert (built_plugin / "commands" / "setup.md").is_file()


def test_setup_command_has_frontmatter(built_plugin: Path):
    text = (built_plugin / "commands" / "setup.md").read_text()
    assert text.startswith("---\n")


def test_setup_command_describes_action(built_plugin: Path):
    text = (built_plugin / "commands" / "setup.md").read_text()
    assert "setup.sh" in text or "install" in text.lower()
