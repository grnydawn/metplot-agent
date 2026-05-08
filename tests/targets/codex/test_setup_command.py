from pathlib import Path


def test_setup_command_present(built_plugin: Path):
    assert (built_plugin / "commands" / "setup.md").is_file()


def test_user_invocable_flag(built_plugin: Path):
    text = (built_plugin / "commands" / "setup.md").read_text()
    assert "user-invocable: true" in text
