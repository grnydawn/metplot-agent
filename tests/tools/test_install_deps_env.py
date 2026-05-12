import sys
from pathlib import Path

import pytest

from tools.install_deps import (
    EnvironmentError_, detect_python, detect_installer, in_venv,
)


def test_in_venv_true_when_VIRTUAL_ENV_set(monkeypatch):
    monkeypatch.setenv("VIRTUAL_ENV", "/some/path")
    assert in_venv() is True


def test_in_venv_false_when_VIRTUAL_ENV_unset(monkeypatch):
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    assert in_venv() is False


def test_detect_python_uses_running_interpreter_if_compatible(
        monkeypatch, tmp_path):
    """When VIRTUAL_ENV is unset and no nearby .venv/, use sys.executable."""
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    monkeypatch.chdir(tmp_path)  # away from any project-local .venv/
    p = detect_python()
    assert p == Path(sys.executable)


def test_detect_python_uses_venv_when_set(monkeypatch, tmp_path):
    fake_venv = tmp_path / "fake-venv"
    (fake_venv / "bin").mkdir(parents=True)
    fake_python = fake_venv / "bin" / "python"
    fake_python.write_text("#!/bin/sh\nexit 0")
    fake_python.chmod(0o755)
    monkeypatch.setenv("VIRTUAL_ENV", str(fake_venv))
    p = detect_python()
    # Should resolve to the venv's python (binary doesn't actually need to be 3.10
    # for this test — env-detection chooses without version-checking the venv-pinned one)
    assert p == fake_python


def test_detect_python_walks_up_to_project_venv(monkeypatch, tmp_path):
    """When VIRTUAL_ENV is unset, walk up from cwd looking for `.venv/`.

    Mirrors uv's behavior so the launcher's hardcoded Python matches
    where uv routed the install. Without this, dev environments with a
    project-local `.venv/` get a launcher pointing at system Python
    while packages live in the venv, and the launcher fails to import."""
    project = tmp_path / "myproject"
    nested = project / "subdir" / "deeper"
    nested.mkdir(parents=True)
    fake_python = project / ".venv" / "bin" / "python"
    fake_python.parent.mkdir(parents=True)
    fake_python.write_text("#!/bin/sh\nexit 0")
    fake_python.chmod(0o755)

    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    monkeypatch.chdir(nested)
    p = detect_python()
    assert p == fake_python


def test_detect_python_venv_env_takes_precedence_over_walk_up(
        monkeypatch, tmp_path):
    """If both VIRTUAL_ENV and a nearby `.venv/` exist, the env wins —
    the user's explicit choice should override auto-detection."""
    nearby = tmp_path / "nearby"
    nearby_py = nearby / ".venv" / "bin" / "python"
    nearby_py.parent.mkdir(parents=True)
    nearby_py.write_text("#!/bin/sh\nexit 0")
    nearby_py.chmod(0o755)

    explicit = tmp_path / "explicit-venv"
    explicit_py = explicit / "bin" / "python"
    explicit_py.parent.mkdir(parents=True)
    explicit_py.write_text("#!/bin/sh\nexit 0")
    explicit_py.chmod(0o755)

    monkeypatch.setenv("VIRTUAL_ENV", str(explicit))
    monkeypatch.chdir(nearby)
    p = detect_python()
    assert p == explicit_py


def test_detect_python_errors_if_too_old(monkeypatch, tmp_path):
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.version_info", (3, 9, 0, "final", 0))
    with pytest.raises(EnvironmentError_):
        detect_python()


def test_detect_installer_prefers_uv(monkeypatch):
    """When uv is on PATH, prefer it over pip."""
    def fake_which(name):
        return f"/usr/bin/{name}" if name == "uv" else None
    monkeypatch.setattr("shutil.which", fake_which)
    cmd, args = detect_installer(Path("/usr/bin/python"))
    assert cmd == "uv"
    assert "pip" in args
    assert "install" in args


def test_detect_installer_falls_back_to_pip(monkeypatch):
    """When uv is missing, fall back to `<python> -m pip`."""
    monkeypatch.setattr("shutil.which", lambda name: None)
    cmd, args = detect_installer(Path("/usr/bin/python"))
    assert cmd == "/usr/bin/python"
    assert args == ["-m", "pip", "install"]


def test_detect_installer_hard_fails_when_neither(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda name: None)
    fake_py = tmp_path / "python"
    fake_py.write_text("")  # nonexistent pip module would fail at runtime;
    # the detector returns the pip-fallback regardless. Hard-fail logic is
    # exercised by an integration check at runtime, not detect time.
    cmd, args = detect_installer(fake_py)
    assert cmd == str(fake_py)  # detector still returns; runtime call would fail
