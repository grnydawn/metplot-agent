"""Cycle-5 helper: copy install tooling into a target plugin payload.

Each target's build.py calls `copy_install_tooling(repo_root, plugin_dir)`
which lays down:
- tools/install_deps.py (verbatim copy of the canonical installer)
- setup.sh (bash wrapper)
- setup.ps1 (PowerShell wrapper)
"""
from __future__ import annotations

import shutil
import stat
from pathlib import Path

from targets._common.setup_sh import SETUP_SH, SETUP_PS1


def copy_install_tooling(repo_root: Path, plugin_dir: Path) -> None:
    """Copy install_deps.py + setup.sh + setup.ps1 into plugin_dir."""
    src_installer = repo_root / "tools" / "install_deps.py"
    if not src_installer.is_file():
        raise RuntimeError(
            f"missing canonical installer at {src_installer}; "
            "did you forget to ship cycle-5?"
        )

    tools_dir = plugin_dir / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_installer, tools_dir / "install_deps.py")

    setup_sh = plugin_dir / "setup.sh"
    setup_sh.write_text(SETUP_SH)
    # Make executable
    setup_sh.chmod(setup_sh.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    setup_ps1 = plugin_dir / "setup.ps1"
    setup_ps1.write_text(SETUP_PS1)
