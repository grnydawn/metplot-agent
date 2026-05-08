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
