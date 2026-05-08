"""End-to-end --dry-run: invoke the installer, verify it prints
the install plan without executing subprocess calls."""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_dry_run_lists_default_plan(tmp_path):
    """A dry-run with default flags prints all 4 steps."""
    fake_mcp = tmp_path / "mcp-servers"
    (fake_mcp / "netcdf_reader").mkdir(parents=True)
    (fake_mcp / "plot_renderer").mkdir(parents=True)
    (fake_mcp / "netcdf_reader" / "pyproject.toml").write_text("[project]\nname='x'\n")
    (fake_mcp / "plot_renderer" / "pyproject.toml").write_text("[project]\nname='y'\n")

    result = subprocess.run(
        [sys.executable, "-m", "tools.install_deps",
         "--dry-run", "--mcp-servers-dir", str(fake_mcp)],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0
    out = result.stdout
    assert "netcdf-reader" in out
    assert "plot-renderer" in out
    assert "cartopy" in out
    assert "scipy" in out
    assert "dry-run" in out


def test_dry_run_no_optionals(tmp_path):
    """--no-cartopy --no-scipy keeps only the required steps."""
    fake_mcp = tmp_path / "mcp-servers"
    (fake_mcp / "netcdf_reader").mkdir(parents=True)
    (fake_mcp / "plot_renderer").mkdir(parents=True)

    result = subprocess.run(
        [sys.executable, "-m", "tools.install_deps",
         "--dry-run", "--no-cartopy", "--no-scipy",
         "--mcp-servers-dir", str(fake_mcp)],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0
    out = result.stdout
    assert "netcdf-reader" in out
    assert "plot-renderer" in out
    assert "cartopy" not in out
    assert "scipy" not in out
