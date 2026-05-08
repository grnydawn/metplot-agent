import stat
from pathlib import Path

import pytest

from targets._common.install_tooling import copy_install_tooling


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_copies_install_deps(tmp_path):
    copy_install_tooling(REPO_ROOT, tmp_path)
    assert (tmp_path / "tools" / "install_deps.py").is_file()


def test_writes_setup_sh_executable(tmp_path):
    copy_install_tooling(REPO_ROOT, tmp_path)
    sh = tmp_path / "setup.sh"
    assert sh.is_file()
    mode = sh.stat().st_mode
    assert mode & stat.S_IXUSR  # owner-executable


def test_writes_setup_ps1(tmp_path):
    copy_install_tooling(REPO_ROOT, tmp_path)
    assert (tmp_path / "setup.ps1").is_file()


def test_setup_sh_references_install_deps(tmp_path):
    copy_install_tooling(REPO_ROOT, tmp_path)
    sh_text = (tmp_path / "setup.sh").read_text()
    assert "tools/install_deps.py" in sh_text
    assert "mcp-servers" in sh_text


def test_raises_when_canonical_installer_missing(tmp_path):
    fake_root = tmp_path / "fake-repo"
    fake_root.mkdir()
    out = tmp_path / "plugin"
    out.mkdir()
    with pytest.raises(RuntimeError):
        copy_install_tooling(fake_root, out)
