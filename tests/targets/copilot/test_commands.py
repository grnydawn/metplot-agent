from pathlib import Path


def test_refine_md_present(built_plugin: Path):
    assert (built_plugin / "commands" / "refine.md").is_file()


def test_refine_has_frontmatter(built_plugin: Path):
    text = (built_plugin / "commands" / "refine.md").read_text()
    assert text.startswith("---\n")


def test_refine_announces_placeholder(built_plugin: Path):
    text = (built_plugin / "commands" / "refine.md").read_text()
    assert "placeholder" in text.lower() or "cycle 6" in text.lower()


def test_setup_command_present(built_plugin: Path):
    assert (built_plugin / "commands" / "setup.md").is_file()


def test_setup_command_user_invocable(built_plugin: Path):
    text = (built_plugin / "commands" / "setup.md").read_text()
    assert "user-invocable: true" in text
