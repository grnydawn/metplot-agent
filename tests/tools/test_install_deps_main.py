import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from tools.install_deps import main, EXIT_OK, EXIT_REQUIRED_FAILED, EXIT_BAD_ENV


def _fake_subprocess(returncode: int = 0):
    def fake_run(*args, **kwargs):
        m = MagicMock()
        m.returncode = returncode
        return m
    return fake_run


def test_main_dry_run_prints_plan_exits_zero(capsys, tmp_path, monkeypatch):
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    rc = main(["--dry-run", "--mcp-servers-dir", str(tmp_path),
                "--no-cartopy", "--no-scipy"])
    out = capsys.readouterr().out
    assert rc == EXIT_OK
    assert "netcdf-reader" in out
    assert "plot-renderer" in out


def test_main_succeeds_when_all_steps_succeed(monkeypatch, tmp_path):
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    monkeypatch.setattr("subprocess.run", _fake_subprocess(returncode=0))
    rc = main(["--mcp-servers-dir", str(tmp_path)])
    assert rc == EXIT_OK


def test_main_fails_when_required_step_fails(monkeypatch, tmp_path):
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    monkeypatch.setattr("subprocess.run", _fake_subprocess(returncode=1))
    rc = main(["--mcp-servers-dir", str(tmp_path)])
    assert rc == EXIT_REQUIRED_FAILED


def test_main_warns_but_succeeds_when_optional_fails(monkeypatch, tmp_path):
    """Optional cartopy/scipy fail -> warn but exit 0."""
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    call_count = {"n": 0}
    def selective_fail(*args, **kwargs):
        call_count["n"] += 1
        m = MagicMock()
        # First 2 (required) succeed; cartopy fails
        m.returncode = 1 if call_count["n"] == 3 else 0
        return m
    monkeypatch.setattr("subprocess.run", selective_fail)
    rc = main(["--mcp-servers-dir", str(tmp_path), "--no-scipy"])
    assert rc == EXIT_OK   # cartopy is optional


def test_main_bad_env_when_python_too_old(monkeypatch, tmp_path):
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    monkeypatch.setattr("sys.version_info", (3, 9, 0, "final", 0))
    rc = main(["--mcp-servers-dir", str(tmp_path)])
    assert rc == EXIT_BAD_ENV
