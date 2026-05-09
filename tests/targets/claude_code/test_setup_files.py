import stat
from pathlib import Path


def test_setup_sh_present(built_plugin: Path):
    sh = built_plugin / "setup.sh"
    assert sh.is_file()


def test_setup_sh_executable(built_plugin: Path):
    mode = (built_plugin / "setup.sh").stat().st_mode
    assert mode & stat.S_IXUSR


def test_setup_ps1_present(built_plugin: Path):
    assert (built_plugin / "setup.ps1").is_file()


def test_install_deps_bundled(built_plugin: Path):
    assert (built_plugin / "tools" / "install_deps.py").is_file()


def test_bin_dir_pre_created(built_plugin: Path):
    """Build pre-creates `bin/` so Claude Code adds it to PATH at plugin
    load time. setup.sh fills it with launcher shims during SessionStart
    so .mcp.json's bare command names resolve without venv activation."""
    bin_dir = built_plugin / "bin"
    assert bin_dir.is_dir(), "bin/ must exist before SessionStart fires"


def test_setup_sh_passes_launcher_dir(built_plugin: Path):
    """setup.sh must pass --launcher-dir to install_deps so launchers
    get written when SessionStart fires."""
    sh_text = (built_plugin / "setup.sh").read_text()
    assert "--launcher-dir" in sh_text, (
        "setup.sh missing --launcher-dir; .mcp.json bare commands "
        "won't resolve without venv on PATH")
    assert '"$SCRIPT_DIR/bin"' in sh_text


def test_setup_ps1_passes_launcher_dir(built_plugin: Path):
    """setup.ps1 must pass --launcher-dir for Windows users."""
    ps1_text = (built_plugin / "setup.ps1").read_text()
    assert "--launcher-dir" in ps1_text
    assert '"$ScriptDir/bin"' in ps1_text
