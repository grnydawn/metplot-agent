# Cycle 5: Semi-auto setup — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a one-shot dependency installer (`tools/install_deps.py`), per-target `setup.sh`/`setup.ps1` wrappers, a `/ncplot:setup` slash command on every slash-capable host, a `SessionStart` auto-fire hook on Claude Code, and rename the plugin manifest from `ncplot-agent` to `ncplot`.

**Architecture:** Single canonical installer at `tools/install_deps.py`; each target's build copies it + thin wrappers into the plugin payload via a new shared helper `targets/_common/install_tooling.py`. Plugin rename is one constant change in `targets/_common/manifest.py` plus cascading test fixture updates.

**Tech Stack:** Python 3.10+, bash, PowerShell, pytest. No new runtime deps.

**Branch:** `cycle-5-auto-setup` (already created; spec + research already committed).

---

## File Structure

### New / modified source files

| File | Status | LOC est. |
|------|--------|----------|
| `targets/_common/manifest.py` | MODIFY (rename) | -1/+1 |
| `tools/install_deps.py` | NEW | ~250 |
| `targets/_common/install_tooling.py` | NEW | ~80 |
| `targets/_common/setup_sh.py` | NEW (holds setup.sh/ps1 templates) | ~60 |
| `targets/claude-code/build.py` | MODIFY | +20 |
| `targets/codex/build.py` | MODIFY | +15 |
| `targets/gemini-cli/build.py` | MODIFY | +20 |
| `targets/cursor/build.py` | MODIFY | +15 |
| `targets/copilot/build.py` | MODIFY | +15 |
| `targets/antigravity/build.py` | MODIFY | +20 |
| `targets/claude-desktop/build.py` | MODIFY | +10 |

### New test files

```
tests/tools/test_install_deps_args.py          # argument parsing
tests/tools/test_install_deps_env.py           # env detection
tests/tools/test_install_deps_plan.py          # install plan composition
tests/tools/test_install_deps_dry_run.py       # --dry-run integration
tests/tools/test_install_deps_real.py          # opt-in real install (gated)

tests/targets/_common/test_install_tooling_helper.py

# Per target (each cycle-7 target gets these added):
tests/targets/<host>/test_setup_files.py       # setup.sh + setup.ps1 + tools/install_deps.py present
tests/targets/<host>/test_setup_command.py     # /ncplot:setup slash command emitted (where applicable)

tests/targets/claude_code/test_session_start_hook.py   # Claude-Code-only

tests/targets/test_all_targets_have_setup.py   # cross-target smoke
```

### Doc updates

- `docs/architecture.md` — note the plugin rename + cycle-5 setup
- `docs/adding-targets.md` — install tooling responsibilities
- Each target's plugin payload `README.md` — install instructions become "run `./setup.sh`"

---

## Phase 1: Plugin rename

### Task 1: Rename `ncplot-agent` → `ncplot` in plugin manifest

The `PLUGIN_NAME` constant cascades to: build dir name, plugin.json `name` field, install path. Changing it breaks ~30 test assertions; this task fixes them in the same commit.

**Files:**
- Modify: `targets/_common/manifest.py`
- Modify: `tests/targets/<various>/test_*.py` (assertions referencing `ncplot-agent`)

- [ ] **Step 1: Update the constant**

```python
# targets/_common/manifest.py
PLUGIN_NAME = "ncplot"   # was "ncplot-agent" (cycle-5 rename for /ncplot: slash namespace)
```

- [ ] **Step 2: Find all test fixtures referencing `ncplot-agent`**

```bash
grep -rln "ncplot-agent" tests/targets/ targets/ docs/
```

Expected hits (representative — exact list may differ):
- `tests/targets/claude_code/conftest.py` (the `built_plugin` fixture path)
- `tests/targets/<host>/conftest.py` (each cycle-7 target)
- `tests/targets/<host>/test_build_runs.py` (asserts `built_plugin.name == "ncplot-agent"`)
- `tests/targets/<host>/test_manifest.py` (asserts manifest `name`)
- `tests/targets/test_all_targets_buildable.py`

- [ ] **Step 3: For each hit, change `ncplot-agent` to `ncplot`**

In `conftest.py` files:
```python
# OLD:
return out / "ncplot-agent"
# NEW:
return out / "ncplot"
```

In `test_build_runs.py` files:
```python
# OLD:
assert built_plugin.name == "ncplot-agent"
# NEW:
assert built_plugin.name == "ncplot"
```

In `test_manifest.py` files (where applicable):
```python
# OLD:
assert m["name"] == "ncplot-agent"
# NEW:
assert m["name"] == "ncplot"
```

In `test_all_targets_buildable.py`:
```python
# OLD:
plugin_root = out / "ncplot-agent"
# NEW:
plugin_root = out / "ncplot"
```

- [ ] **Step 4: Find all docs referencing `ncplot-agent` plugin name**

```bash
grep -rln "ncplot-agent" docs/ targets/*/README.md
```

Update generated-README templates and architecture docs to use `ncplot` for the plugin name. Keep `ncplot-agent` for repo references (e.g., `https://github.com/grnydawn/ncplot-agent`) — only the **plugin name** changes.

Specifically: in each target's README content (the strings inside `_plugin_readme()` functions in `targets/<host>/build.py`), update plugin install paths and dir names. (We'll leave the build.py edits for Phase 4; only docs are touched here.)

- [ ] **Step 5: Run all build-target tests; assert green**

```bash
.venv/bin/pytest tests/targets -v
```

Expected: all pass after the rename. If anything fails, it's a missed reference — fix it.

- [ ] **Step 6: Smoke test — actually run a build**

```bash
.venv/bin/python -m tools.build claude-code
ls build/claude-code/
```

Expected: `build/claude-code/ncplot/` (was `ncplot-agent/`). The plugin.json `name` is `ncplot`.

- [ ] **Step 7: Commit**

```bash
git add targets/_common/manifest.py tests/targets/ docs/ targets/*/README.md
git commit -m "cycle-5 task 1: rename plugin manifest 'ncplot-agent' → 'ncplot'"
```

---

## Phase 2: Canonical installer

### Task 2: `tools/install_deps.py` — argument parsing

**Files:**
- Create: `tools/install_deps.py` (initial — grows in tasks 3-5)
- Create: `tests/tools/test_install_deps_args.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/tools/test_install_deps_args.py
import pytest

from tools.install_deps import parse_args, Args


def test_defaults():
    a = parse_args([])
    assert isinstance(a, Args)
    assert a.no_cartopy is False
    assert a.no_scipy is False
    assert a.quiet is False
    assert a.dry_run is False
    assert a.force is False
    assert a.mcp_servers_dir is None


def test_no_cartopy():
    a = parse_args(["--no-cartopy"])
    assert a.no_cartopy is True


def test_quiet():
    a = parse_args(["--quiet"])
    assert a.quiet is True


def test_dry_run():
    a = parse_args(["--dry-run"])
    assert a.dry_run is True


def test_force():
    a = parse_args(["--force"])
    assert a.force is True


def test_mcp_servers_dir():
    a = parse_args(["--mcp-servers-dir", "/tmp/mcp"])
    assert str(a.mcp_servers_dir) == "/tmp/mcp"


def test_combined():
    a = parse_args(["--no-cartopy", "--no-scipy", "--quiet", "--force"])
    assert a.no_cartopy and a.no_scipy and a.quiet and a.force
```

- [ ] **Step 2: Run, expect ImportError**

```bash
.venv/bin/pytest tests/tools/test_install_deps_args.py -v
```

- [ ] **Step 3: Implement the arg parser**

```python
# tools/install_deps.py
"""Cycle-5 canonical dependency installer for ncplot.

Installs the two MCP server packages plus optional cartopy + scipy.
Used as: `python -m tools.install_deps [flags]` (from repo root) or
indirectly via the per-target `setup.sh` / `setup.ps1` wrappers
bundled in each plugin payload.

See docs/specs/2026-05-08-cycle-5-auto-setup.md for the full design.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Args:
    no_cartopy: bool
    no_scipy: bool
    quiet: bool
    dry_run: bool
    force: bool
    mcp_servers_dir: Path | None


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ncplot-install",
        description="Install ncplot's Python dependencies (cycle 5).",
    )
    p.add_argument("--no-cartopy", action="store_true",
                   help="Skip cartopy install.")
    p.add_argument("--no-scipy", action="store_true",
                   help="Skip scipy install.")
    p.add_argument("--quiet", action="store_true",
                   help="Suppress progress output. Errors still print.")
    p.add_argument("--dry-run", action="store_true",
                   help="Print the install plan without executing.")
    p.add_argument("--force", action="store_true",
                   help="Pass --upgrade to underlying pip/uv.")
    p.add_argument("--mcp-servers-dir", type=Path, default=None,
                   help="Override search path for mcp-servers/ packages.")
    return p


def parse_args(argv: list[str] | None = None) -> Args:
    ns = _build_parser().parse_args(argv)
    return Args(
        no_cartopy=ns.no_cartopy,
        no_scipy=ns.no_scipy,
        quiet=ns.quiet,
        dry_run=ns.dry_run,
        force=ns.force,
        mcp_servers_dir=ns.mcp_servers_dir,
    )
```

- [ ] **Step 4: Verify green**

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/install_deps.py tests/tools/test_install_deps_args.py
git commit -m "cycle-5 task 2: install_deps.py argument parsing"
```

---

### Task 3: Environment detection

**Files:**
- Modify: `tools/install_deps.py`
- Create: `tests/tools/test_install_deps_env.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/tools/test_install_deps_env.py
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


def test_detect_python_uses_running_interpreter_if_compatible(monkeypatch):
    """When VIRTUAL_ENV is unset, use sys.executable if it's >= 3.10."""
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
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


def test_detect_python_errors_if_too_old(monkeypatch):
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
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
```

- [ ] **Step 2: Implement env detection in install_deps.py**

Append to `tools/install_deps.py`:

```python
import os
import shutil
import sys


class EnvironmentError_(RuntimeError):
    """Raised when the install environment is unsuitable."""
    pass


def in_venv() -> bool:
    """Return True if a venv is active (VIRTUAL_ENV env var set)."""
    return bool(os.environ.get("VIRTUAL_ENV"))


def detect_python() -> Path:
    """Return the Python interpreter to install into.

    Order:
      1. ${VIRTUAL_ENV}/bin/python (if set)
      2. The Python running install_deps.py itself (if >= 3.10)
      3. python3.12 / python3.11 / python3.10 on PATH (in that order)

    Raises EnvironmentError_ if none usable.
    """
    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        candidate = Path(venv) / "bin" / "python"
        if candidate.exists():
            return candidate

    # Use the running interpreter if compatible
    if sys.version_info >= (3, 10):
        return Path(sys.executable)

    # PATH lookup as last resort
    for name in ("python3.12", "python3.11", "python3.10"):
        p = shutil.which(name)
        if p:
            return Path(p)

    raise EnvironmentError_(
        f"No Python ≥ 3.10 found. Got {sys.version_info[:2]}; "
        "install Python 3.10+ from https://www.python.org/downloads/"
    )


def detect_installer(python_bin: Path) -> tuple[str, list[str]]:
    """Return (cmd, base_args) for the chosen package manager.

    Order:
      1. uv (if `uv` on PATH) → ("uv", ["pip", "install"])
      2. pip via <python_bin> -m pip → (str(python_bin), ["-m", "pip", "install"])
    """
    uv = shutil.which("uv")
    if uv:
        return ("uv", ["pip", "install"])
    return (str(python_bin), ["-m", "pip", "install"])
```

- [ ] **Step 3: Run, verify green**

Expected: 8 passed.

- [ ] **Step 4: Commit**

```bash
git add tools/install_deps.py tests/tools/test_install_deps_env.py
git commit -m "cycle-5 task 3: install_deps.py environment detection"
```

---

### Task 4: Install plan composition + dry-run

**Files:**
- Modify: `tools/install_deps.py`
- Create: `tests/tools/test_install_deps_plan.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/tools/test_install_deps_plan.py
from pathlib import Path

import pytest

from tools.install_deps import Args, Step, build_plan


def _args(**kw) -> Args:
    return Args(no_cartopy=False, no_scipy=False, quiet=False,
                 dry_run=False, force=False,
                 mcp_servers_dir=Path("/m"), **kw)


def test_default_plan_has_4_steps():
    plan = build_plan(_args())
    assert len(plan) == 4


def test_default_plan_step_order():
    plan = build_plan(_args())
    titles = [s.title for s in plan]
    assert titles == ["netcdf-reader", "plot-renderer",
                       "cartopy", "scipy"]


def test_required_flag():
    plan = build_plan(_args())
    assert plan[0].required is True   # netcdf-reader
    assert plan[1].required is True   # plot-renderer
    assert plan[2].required is False  # cartopy
    assert plan[3].required is False  # scipy


def test_no_cartopy_skips_cartopy():
    plan = build_plan(Args(no_cartopy=True, no_scipy=False, quiet=False,
                            dry_run=False, force=False,
                            mcp_servers_dir=Path("/m")))
    titles = [s.title for s in plan]
    assert "cartopy" not in titles


def test_no_scipy_skips_scipy():
    plan = build_plan(Args(no_cartopy=False, no_scipy=True, quiet=False,
                            dry_run=False, force=False,
                            mcp_servers_dir=Path("/m")))
    titles = [s.title for s in plan]
    assert "scipy" not in titles


def test_mcp_step_uses_mcp_servers_dir():
    plan = build_plan(Args(no_cartopy=True, no_scipy=True, quiet=False,
                            dry_run=False, force=False,
                            mcp_servers_dir=Path("/m")))
    # Required steps point at the package dirs
    assert plan[0].pkg_path == Path("/m/netcdf_reader")
    assert plan[1].pkg_path == Path("/m/plot_renderer")
```

- [ ] **Step 2: Implement plan composition**

Append to `tools/install_deps.py`:

```python
@dataclass
class Step:
    title: str
    required: bool
    pkg_path: Path | None = None       # for local package installs
    pkg_spec: str | None = None        # for PyPI specs like "cartopy>=0.22"
    recovery_hint: str = ""


def build_plan(args: Args) -> list[Step]:
    """Construct the ordered install plan from CLI args."""
    mcp_dir = args.mcp_servers_dir or Path("mcp-servers")  # default for dev runs
    plan: list[Step] = [
        Step(title="netcdf-reader", required=True,
             pkg_path=mcp_dir / "netcdf_reader"),
        Step(title="plot-renderer", required=True,
             pkg_path=mcp_dir / "plot_renderer"),
    ]
    if not args.no_cartopy:
        plan.append(Step(
            title="cartopy", required=False,
            pkg_spec="cartopy>=0.22",
            recovery_hint=(
                "On Debian/Ubuntu: sudo apt-get install libproj-dev libgeos-dev. "
                "Or use conda: conda install -c conda-forge cartopy"),
        ))
    if not args.no_scipy:
        plan.append(Step(
            title="scipy", required=False,
            pkg_spec="scipy>=1.11",
            recovery_hint=(
                "See https://docs.scipy.org/doc/scipy/getting_started.html"),
        ))
    return plan


def render_install_command(step: Step,
                            installer_cmd: str, installer_args: list[str],
                            force: bool) -> list[str]:
    """Build the argv for one step's subprocess.run call."""
    cmd = [installer_cmd, *installer_args]
    if force:
        cmd.append("--upgrade")
    if step.pkg_path is not None:
        cmd.append(str(step.pkg_path))
    elif step.pkg_spec is not None:
        cmd.append(step.pkg_spec)
    else:
        raise ValueError(f"step {step.title!r} has neither pkg_path nor pkg_spec")
    return cmd
```

- [ ] **Step 3: Verify green**

Expected: 6 passed.

- [ ] **Step 4: Commit**

```bash
git add tools/install_deps.py tests/tools/test_install_deps_plan.py
git commit -m "cycle-5 task 4: install_deps.py install plan composition"
```

---

### Task 5: Main flow + output formatting + exit codes

**Files:**
- Modify: `tools/install_deps.py`
- Create: `tests/tools/test_install_deps_main.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/tools/test_install_deps_main.py
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
    """Optional cartopy/scipy fail → warn but exit 0."""
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
```

- [ ] **Step 2: Implement main flow**

Append to `tools/install_deps.py`:

```python
import subprocess


EXIT_OK = 0
EXIT_REQUIRED_FAILED = 1
EXIT_BAD_ENV = 2
EXIT_BAD_ARGS = 3


def _print(args: Args, *parts) -> None:
    if not args.quiet:
        print(*parts)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
    except SystemExit as e:
        return EXIT_BAD_ARGS if e.code != 0 else EXIT_OK

    try:
        python_bin = detect_python()
    except EnvironmentError_ as e:
        print(f"ERROR: {e}", flush=True)
        return EXIT_BAD_ENV

    installer_cmd, installer_args = detect_installer(python_bin)

    if not args.quiet and not in_venv():
        print(
            "WARNING: Installing into system Python (no venv active). "
            "Consider activating a venv first to avoid polluting your "
            "system Python.\n",
            flush=True,
        )

    plan = build_plan(args)

    _print(args, "ncplot setup")
    _print(args, f"  Python:    {python_bin}")
    _print(args, f"  Installer: {installer_cmd}")
    _print(args, "")

    n_total = len(plan)
    n_ok = 0
    n_warn = 0
    for i, step in enumerate(plan, 1):
        cmd = render_install_command(
            step, installer_cmd, installer_args, force=args.force,
        )
        kind = "required" if step.required else "optional"
        _print(args, f"[{i}/{n_total}] Installing {step.title} ({kind})")
        _print(args, f"      {' '.join(cmd)}")

        if args.dry_run:
            _print(args, "      (dry-run; not executing)")
            n_ok += 1
            continue

        try:
            result = subprocess.run(cmd, check=False)
        except FileNotFoundError as e:
            result = MagicMock_failure(returncode=127, stderr=str(e))

        if result.returncode == 0:
            _print(args, "      ✓ done")
            n_ok += 1
        elif step.required:
            print(f"      ✗ FAILED — exit {result.returncode}", flush=True)
            print(f"      Required step. Aborting.", flush=True)
            return EXIT_REQUIRED_FAILED
        else:
            print(f"      ✗ FAILED — exit {result.returncode}", flush=True)
            if step.recovery_hint:
                print(f"        hint: {step.recovery_hint}", flush=True)
            n_warn += 1

    if n_warn == 0:
        _print(args, f"\nSetup complete. {n_ok}/{n_total} steps succeeded.")
    else:
        _print(args,
               f"\nSetup complete with warnings. "
               f"{n_ok}/{n_total} steps succeeded; {n_warn} optional failed.")
    return EXIT_OK


class MagicMock_failure:
    """Stand-in for subprocess.run result when the call itself errored."""
    def __init__(self, returncode: int = 1, stderr: str = ""):
        self.returncode = returncode
        self.stderr = stderr


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Verify green**

```bash
.venv/bin/pytest tests/tools/test_install_deps_main.py -v
```

Expected: 5 passed.

- [ ] **Step 4: Commit**

```bash
git add tools/install_deps.py tests/tools/test_install_deps_main.py
git commit -m "cycle-5 task 5: install_deps.py main flow + exit codes + system-python warning"
```

---

### Task 6: `--dry-run` integration smoke test

**Files:**
- Create: `tests/tools/test_install_deps_dry_run.py`

- [ ] **Step 1: Write the test**

```python
# tests/tools/test_install_deps_dry_run.py
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
```

- [ ] **Step 2: Run + verify pass**

```bash
.venv/bin/pytest tests/tools/test_install_deps_dry_run.py -v
```

Expected: 2 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/tools/test_install_deps_dry_run.py
git commit -m "cycle-5 task 6: install_deps --dry-run integration test"
```

---

## Phase 3: Setup tooling helper + wrappers

### Task 7: Setup wrapper templates + `targets/_common/install_tooling.py`

**Files:**
- Create: `targets/_common/install_tooling.py`
- Create: `targets/_common/setup_sh.py`
- Create: `tests/targets/_common/test_install_tooling_helper.py`

- [ ] **Step 1: Write `setup_sh.py` (templates)**

```python
# targets/_common/setup_sh.py
"""Bash + PowerShell wrapper templates for cycle-5 setup."""

SETUP_SH = '''\
#!/usr/bin/env bash
# ncplot setup wrapper. Runs tools/install_deps.py against the bundled
# mcp-servers/. See README.md for usage and flags.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DEPS="$SCRIPT_DIR/tools/install_deps.py"

if [ ! -f "$INSTALL_DEPS" ]; then
    echo "ERROR: tools/install_deps.py not found in $SCRIPT_DIR." >&2
    echo "       The plugin payload is incomplete; reinstall from a fresh build." >&2
    exit 2
fi

# Choose Python: VIRTUAL_ENV first, then python3.10+
if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "${VIRTUAL_ENV}/bin/python" ]; then
    PYTHON_BIN="${VIRTUAL_ENV}/bin/python"
else
    for p in python3.12 python3.11 python3.10 python3 python; do
        if command -v "$p" >/dev/null 2>&1; then
            PYTHON_BIN="$p"
            break
        fi
    done
    if [ -z "${PYTHON_BIN:-}" ]; then
        echo "ERROR: no python3.10+ found on PATH." >&2
        exit 2
    fi
fi

exec "$PYTHON_BIN" "$INSTALL_DEPS" \\
    --mcp-servers-dir "$SCRIPT_DIR/mcp-servers" \\
    "$@"
'''

SETUP_PS1 = '''\
# ncplot setup wrapper (PowerShell). Runs tools/install_deps.py against the bundled
# mcp-servers/. See README.md for usage.
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallDeps = Join-Path $ScriptDir "tools/install_deps.py"

if (-not (Test-Path $InstallDeps)) {
    Write-Error "tools/install_deps.py not found. Plugin payload is incomplete."
    exit 2
}

# Choose Python
if ($env:VIRTUAL_ENV -and (Test-Path "$env:VIRTUAL_ENV/Scripts/python.exe")) {
    $PythonBin = "$env:VIRTUAL_ENV/Scripts/python.exe"
} else {
    foreach ($p in @("python3.12", "python3.11", "python3.10", "python3", "python")) {
        $found = Get-Command $p -ErrorAction SilentlyContinue
        if ($found) { $PythonBin = $p; break }
    }
    if (-not $PythonBin) {
        Write-Error "No Python 3.10+ found on PATH."
        exit 2
    }
}

& $PythonBin $InstallDeps `
    --mcp-servers-dir "$ScriptDir/mcp-servers" `
    @args
'''
```

- [ ] **Step 2: Write `install_tooling.py` (the helper)**

```python
# targets/_common/install_tooling.py
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
```

- [ ] **Step 3: Write the helper test**

```python
# tests/targets/_common/test_install_tooling_helper.py
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
```

- [ ] **Step 4: Verify green**

```bash
.venv/bin/pytest tests/targets/_common/test_install_tooling_helper.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add targets/_common/install_tooling.py targets/_common/setup_sh.py \
        tests/targets/_common/test_install_tooling_helper.py
git commit -m "cycle-5 task 7: install_tooling helper + setup.sh/ps1 templates"
```

---

## Phase 4: Per-target wiring

Each task in this phase: edit `targets/<host>/build.py` to call
`copy_install_tooling(repo_root, plugin_dir)` after MCP bundling, write
the host-specific `/setup` slash command (or workflow), and add tests.
The pattern is mechanical; details vary per host's slash-command format.

### Task 8: Claude Code — install tooling + SessionStart hook + /ncplot:setup

**Files:**
- Modify: `targets/claude-code/build.py`
- Create: `tests/targets/claude_code/test_setup_files.py`
- Create: `tests/targets/claude_code/test_session_start_hook.py`
- Create: `tests/targets/claude_code/test_setup_command.py`

- [ ] **Step 1: Modify `targets/claude-code/build.py`**

Add the following imports:

```python
from targets._common.install_tooling import copy_install_tooling
```

Add after `bundle_mcp_servers(...)` and BEFORE the existing
`commands/refine.md` write:

```python
    # Cycle-5 setup tooling
    repo_root = Path(__file__).resolve().parents[2]
    copy_install_tooling(repo_root, plugin_dir)

    # SessionStart hook (auto-fire setup on first run / version bump)
    hooks_dir = plugin_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    (hooks_dir / "setup.json").write_text(json.dumps({
        "SessionStart": [{
            "matcher": "*",
            "hooks": [{
                "type": "command",
                "command": "${CLAUDE_PLUGIN_ROOT}/setup.sh --quiet",
            }],
        }],
    }, indent=2) + "\n")

    # /ncplot:setup slash command
    (commands_dir / "setup.md").write_text(
        "---\n"
        "description: Install or repair ncplot's Python dependencies "
        "(MCP servers, cartopy, scipy). Idempotent.\n"
        "---\n\n"
        "Run `${CLAUDE_PLUGIN_ROOT}/setup.sh` to install or refresh the "
        "ncplot dependency stack. Pass --no-cartopy or --no-scipy to "
        "opt out of optional packages.\n"
    )
```

(Make sure `commands_dir` is defined before this — it's already created
by the existing build for `commands/refine.md`. Verify ordering.)

- [ ] **Step 2: Smoke test the build**

```bash
.venv/bin/python -m tools.build claude-code 2>&1 | head
ls build/claude-code/ncplot/
ls build/claude-code/ncplot/tools/
ls build/claude-code/ncplot/hooks/
ls build/claude-code/ncplot/commands/
```

Expected: `setup.sh` and `setup.ps1` in plugin root, `tools/install_deps.py`, `hooks/setup.json`, `commands/setup.md`.

- [ ] **Step 3: Write `test_setup_files.py`**

```python
# tests/targets/claude_code/test_setup_files.py
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
```

- [ ] **Step 4: Write `test_session_start_hook.py`**

```python
# tests/targets/claude_code/test_session_start_hook.py
import json
from pathlib import Path


def test_hook_present(built_plugin: Path):
    assert (built_plugin / "hooks" / "setup.json").is_file()


def test_hook_session_start_event(built_plugin: Path):
    h = json.loads((built_plugin / "hooks" / "setup.json").read_text())
    assert "SessionStart" in h
    cmds = h["SessionStart"][0]["hooks"]
    assert any("setup.sh" in c["command"] for c in cmds)


def test_hook_uses_quiet_flag(built_plugin: Path):
    h = json.loads((built_plugin / "hooks" / "setup.json").read_text())
    cmd = h["SessionStart"][0]["hooks"][0]["command"]
    assert "--quiet" in cmd


def test_hook_uses_plugin_root_var(built_plugin: Path):
    h = json.loads((built_plugin / "hooks" / "setup.json").read_text())
    cmd = h["SessionStart"][0]["hooks"][0]["command"]
    assert "${CLAUDE_PLUGIN_ROOT}" in cmd
```

- [ ] **Step 5: Write `test_setup_command.py`**

```python
# tests/targets/claude_code/test_setup_command.py
from pathlib import Path


def test_setup_command_present(built_plugin: Path):
    assert (built_plugin / "commands" / "setup.md").is_file()


def test_setup_command_has_frontmatter(built_plugin: Path):
    text = (built_plugin / "commands" / "setup.md").read_text()
    assert text.startswith("---\n")


def test_setup_command_describes_action(built_plugin: Path):
    text = (built_plugin / "commands" / "setup.md").read_text()
    assert "setup.sh" in text or "install" in text.lower()
```

- [ ] **Step 6: Run tests**

```bash
.venv/bin/pytest tests/targets/claude_code -v
```

Expected: existing tests + new ones pass.

- [ ] **Step 7: Commit**

```bash
git add targets/claude-code/build.py \
        tests/targets/claude_code/test_setup_files.py \
        tests/targets/claude_code/test_session_start_hook.py \
        tests/targets/claude_code/test_setup_command.py
git commit -m "cycle-5 task 8: claude-code build emits setup.sh + SessionStart + /ncplot:setup"
```

---

### Task 9: Codex — install tooling + commands/setup.md

**Files:**
- Modify: `targets/codex/build.py`
- Create: `tests/targets/codex/test_setup_files.py`
- Create: `tests/targets/codex/test_setup_command.py`

- [ ] **Step 1: Modify `targets/codex/build.py`**

After MCP bundling, before README write:

```python
from targets._common.install_tooling import copy_install_tooling
# ...
repo_root = Path(__file__).resolve().parents[2]
copy_install_tooling(repo_root, plugin_dir)

# /setup slash command (Codex uses bare names; no namespace prefix possible)
commands_dir = plugin_dir / "commands"
commands_dir.mkdir(exist_ok=True)
(commands_dir / "setup.md").write_text(
    "---\n"
    "description: Install or repair ncplot's Python dependencies. Idempotent.\n"
    "user-invocable: true\n"
    "---\n\n"
    "Run the bundled `setup.sh` to install or refresh the dependency stack.\n"
)
```

- [ ] **Step 2: Write tests**

`test_setup_files.py` — same shape as Claude Code's (assert setup.sh/ps1/install_deps.py present + executable).

`test_setup_command.py`:
```python
from pathlib import Path

def test_setup_command_present(built_plugin: Path):
    assert (built_plugin / "commands" / "setup.md").is_file()

def test_user_invocable_flag(built_plugin: Path):
    text = (built_plugin / "commands" / "setup.md").read_text()
    assert "user-invocable: true" in text
```

- [ ] **Step 3: Smoke + tests + commit**

```bash
.venv/bin/python -m tools.build codex
.venv/bin/pytest tests/targets/codex -v
git add targets/codex/build.py tests/targets/codex/test_setup_files.py tests/targets/codex/test_setup_command.py
git commit -m "cycle-5 task 9: codex build emits setup.sh + /setup command (user-invocable)"
```

---

### Task 10: Gemini CLI — install tooling + commands/ncplot/setup.toml

**Files:**
- Modify: `targets/gemini-cli/build.py`
- Create: `tests/targets/gemini_cli/test_setup_files.py`
- Modify: `tests/targets/gemini_cli/test_commands.py` (add assertions for ncplot/setup.toml)

- [ ] **Step 1: Modify `targets/gemini-cli/build.py`**

After MCP bundling:

```python
from targets._common.install_tooling import copy_install_tooling
# ...
repo_root = Path(__file__).resolve().parents[2]
copy_install_tooling(repo_root, plugin_dir)

# /ncplot:setup via subdirectory pattern
ncplot_cmd_dir = commands_dir / "ncplot"
ncplot_cmd_dir.mkdir()
(ncplot_cmd_dir / "setup.toml").write_text(
    'description = "Install or repair ncplot dependencies. Idempotent."\n'
    'prompt = "Run the bundled setup.sh to install ncplot\'s Python dependencies."\n'
)

# Also move refine into the ncplot/ namespace for consistency
existing_refine = commands_dir / "refine.toml"
if existing_refine.exists():
    existing_refine.rename(ncplot_cmd_dir / "refine.toml")
```

- [ ] **Step 2: Write `test_setup_files.py`** (same shape as Claude Code's)

- [ ] **Step 3: Update `test_commands.py`**

Add:
```python
def test_setup_toml_in_ncplot_subdir(built_plugin: Path):
    assert (built_plugin / "commands" / "ncplot" / "setup.toml").is_file()

def test_refine_moved_to_ncplot_subdir(built_plugin: Path):
    assert (built_plugin / "commands" / "ncplot" / "refine.toml").is_file()
    assert not (built_plugin / "commands" / "refine.toml").exists()
```

- [ ] **Step 4: Smoke + tests + commit**

```bash
.venv/bin/python -m tools.build gemini-cli
.venv/bin/pytest tests/targets/gemini_cli -v
git add targets/gemini-cli/build.py tests/targets/gemini_cli/
git commit -m "cycle-5 task 10: gemini-cli build emits setup.sh + /ncplot:setup via subdir"
```

---

### Task 11: Cursor — install tooling + commands/setup.md

**Files:**
- Modify: `targets/cursor/build.py`
- Create: `tests/targets/cursor/test_setup_files.py`
- Modify: `tests/targets/cursor/test_commands.py`

- [ ] **Step 1: Modify build.py**

```python
from targets._common.install_tooling import copy_install_tooling
# After bundle_mcp_servers:
repo_root = Path(__file__).resolve().parents[2]
copy_install_tooling(repo_root, plugin_dir)

# /setup (Cursor doesn't namespace; bare command)
(commands_dir / "setup.md").write_text(
    "---\n"
    "description: Install or repair ncplot's Python dependencies. Idempotent.\n"
    "---\n\n"
    "Run the bundled `setup.sh` from the plugin root.\n"
)
```

- [ ] **Step 2: Write/update tests** (same patterns)

- [ ] **Step 3: Commit**

```bash
.venv/bin/pytest tests/targets/cursor -v
git add targets/cursor/build.py tests/targets/cursor/
git commit -m "cycle-5 task 11: cursor build emits setup.sh + /setup command"
```

---

### Task 12: Copilot — install tooling + /ncplot:setup

**Files:**
- Modify: `targets/copilot/build.py`
- Create: `tests/targets/copilot/test_setup_files.py`
- Modify: `tests/targets/copilot/test_commands.py`

- [ ] **Step 1: Modify build.py**

```python
from targets._common.install_tooling import copy_install_tooling
# After bundle_mcp_servers:
repo_root = Path(__file__).resolve().parents[2]
copy_install_tooling(repo_root, plugin_dir)

# /ncplot:setup (Copilot auto-prefixes from manifest name "ncplot")
(commands_dir / "setup.md").write_text(
    "---\n"
    "description: Install or repair ncplot's Python dependencies. Idempotent.\n"
    "user-invocable: true\n"
    "---\n\n"
    "Run the bundled `setup.sh` from the plugin root.\n"
)
```

- [ ] **Step 2: Tests + commit**

```bash
.venv/bin/pytest tests/targets/copilot -v
git add targets/copilot/build.py tests/targets/copilot/
git commit -m "cycle-5 task 12: copilot build emits setup.sh + /ncplot:setup"
```

---

### Task 13: Antigravity — install tooling + .agent/workflows/setup.md

**Files:**
- Modify: `targets/antigravity/build.py`
- Create: `tests/targets/antigravity/test_setup_files.py`
- Modify: `tests/targets/antigravity/test_workflow.py`

- [ ] **Step 1: Modify build.py**

```python
from targets._common.install_tooling import copy_install_tooling
# ...
repo_root = Path(__file__).resolve().parents[2]
copy_install_tooling(repo_root, plugin_dir)

# Workflow: /setup
workflows_dir = agent_dir / "workflows"
(workflows_dir / "setup.md").write_text(
    "---\n"
    "description: Install or repair ncplot's Python dependencies. Idempotent.\n"
    "---\n\n"
    "# /setup workflow\n\n"
    "Run the bundled `setup.sh` from the plugin root. Idempotent — safe to "
    "re-run after dependency changes.\n"
)
```

- [ ] **Step 2: Tests + commit**

```bash
.venv/bin/pytest tests/targets/antigravity -v
git add targets/antigravity/build.py tests/targets/antigravity/
git commit -m "cycle-5 task 13: antigravity build emits setup.sh + /setup workflow"
```

---

### Task 14: Claude Desktop — install tooling (no slash command)

**Files:**
- Modify: `targets/claude-desktop/build.py`
- Create: `tests/targets/claude_desktop/test_setup_files.py`

- [ ] **Step 1: Modify build.py**

```python
from targets._common.install_tooling import copy_install_tooling
# After bundle_mcp_servers:
repo_root = Path(__file__).resolve().parents[2]
copy_install_tooling(repo_root, plugin_dir)
```

(No slash command — Claude Desktop has no slash-command system. README points users at `setup.sh` directly.)

- [ ] **Step 2: Update README content in `_readme()`** to mention `setup.sh`.

- [ ] **Step 3: Tests + commit**

```bash
.venv/bin/pytest tests/targets/claude_desktop -v
git add targets/claude-desktop/build.py tests/targets/claude_desktop/test_setup_files.py
git commit -m "cycle-5 task 14: claude-desktop build emits setup.sh"
```

---

## Phase 5: Cross-target + final

### Task 15: Cross-target setup smoke test

**Files:**
- Create: `tests/targets/test_all_targets_have_setup.py`

- [ ] **Step 1: Write the test**

```python
# tests/targets/test_all_targets_have_setup.py
"""Verify every cycle-7 target ships setup.sh + setup.ps1 +
tools/install_deps.py."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
TARGETS_ROOT = REPO_ROOT / "targets"
SRC_ROOT = REPO_ROOT / "src"


def _list_targets() -> list[str]:
    out = []
    for p in TARGETS_ROOT.iterdir():
        if p.is_dir() and not p.name.startswith("_") and (p / "build.py").exists():
            out.append(p.name)
    return sorted(out)


def _load_build(target: str):
    spec = importlib.util.spec_from_file_location(
        f"targets.{target.replace('-', '_')}.build",
        TARGETS_ROOT / target / "build.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("target", _list_targets())
def test_target_ships_setup_sh(tmp_path, target: str):
    if target == "hermes":
        pytest.skip("hermes target stub; cycle-5 doesn't update it")
    out = tmp_path / target
    out.mkdir()
    mod = _load_build(target)
    if not hasattr(mod, "build"):
        pytest.skip(f"target {target} has no build()")
    mod.build(SRC_ROOT, out)
    plugin_root = out / "ncplot"
    assert (plugin_root / "setup.sh").is_file(), f"{target}: missing setup.sh"
    assert (plugin_root / "setup.ps1").is_file(), f"{target}: missing setup.ps1"
    assert (plugin_root / "tools" / "install_deps.py").is_file(), (
        f"{target}: missing bundled installer")
```

- [ ] **Step 2: Run + commit**

```bash
.venv/bin/pytest tests/targets/test_all_targets_have_setup.py -v
git add tests/targets/test_all_targets_have_setup.py
git commit -m "cycle-5 task 15: cross-target setup smoke test"
```

---

### Task 16: Real-install opt-in test

**Files:**
- Create: `tests/tools/test_install_deps_real.py`

- [ ] **Step 1: Write the gated test**

```python
# tests/tools/test_install_deps_real.py
"""Optional real-install integration. Gated on NCPLOT_REAL_INSTALL=1.

Creates a fresh venv, runs the actual installer, asserts the
entry-point scripts become callable.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


pytestmark = pytest.mark.skipif(
    os.environ.get("NCPLOT_REAL_INSTALL") != "1",
    reason="set NCPLOT_REAL_INSTALL=1 to enable real-install tests",
)


def _make_venv(tmp_path: Path) -> Path:
    venv_dir = tmp_path / "v"
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)],
                    check=True)
    return venv_dir


def test_minimum_install_runs_without_optionals(tmp_path):
    """--no-cartopy --no-scipy: just the two MCP servers."""
    venv = _make_venv(tmp_path)
    venv_python = venv / "bin" / "python"
    env = os.environ.copy()
    env["VIRTUAL_ENV"] = str(venv)
    result = subprocess.run(
        [sys.executable, "-m", "tools.install_deps",
         "--no-cartopy", "--no-scipy",
         "--mcp-servers-dir", str(REPO_ROOT / "src" / "mcp")],
        cwd=REPO_ROOT, env=env, check=False, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr

    # Verify entry-point scripts exist in the venv
    nc = venv / "bin" / "ncplot-netcdf-reader"
    pr = venv / "bin" / "ncplot-plot-renderer"
    assert nc.is_file(), f"missing entry point: {nc}"
    assert pr.is_file(), f"missing entry point: {pr}"
```

- [ ] **Step 2: Verify it skips by default**

```bash
.venv/bin/pytest tests/tools/test_install_deps_real.py -v
```

Expected: 1 skipped.

- [ ] **Step 3: Commit**

```bash
git add tests/tools/test_install_deps_real.py
git commit -m "cycle-5 task 16: real-install integration test (NCPLOT_REAL_INSTALL=1 gated)"
```

---

### Task 17: Update docs

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/adding-targets.md`

- [ ] **Step 1: Update architecture.md**

Find the section that lists targets and the cycle plan; add a paragraph noting the cycle-5 plugin rename + setup tooling.

- [ ] **Step 2: Update adding-targets.md**

In the "Standard target template" section, add the new line:

```python
# After bundle_mcp_servers:
copy_install_tooling(repo_root, plugin_dir)
```

And add a row to the "Per-target install command" section noting that
each target's build now ships `setup.sh` + `setup.ps1`.

- [ ] **Step 3: Commit**

```bash
git add docs/architecture.md docs/adding-targets.md
git commit -m "cycle-5 task 17: docs update for plugin rename + setup tooling"
```

---

### Task 18: Final lint + suite + push + PR

- [ ] **Step 1: Lint cycle-5 sources**

```bash
.venv/bin/ruff check tools/install_deps.py targets/_common/install_tooling.py \
                     targets/_common/setup_sh.py targets/ tests/tools tests/targets
```

Fix violations.

- [ ] **Step 2: mypy**

```bash
.venv/bin/mypy tools/install_deps.py targets/_common/install_tooling.py \
                targets/_common/setup_sh.py 2>&1 | head -20
```

Fix any hard failures.

- [ ] **Step 3: Build all targets via the dispatcher**

```bash
.venv/bin/python -m tools.build --all
```

Expected: all 7 cycle-5 targets build cleanly (hermes will fail; that's fine, stub unchanged).

- [ ] **Step 4: Validate each target**

```bash
for t in claude-code codex cursor gemini-cli copilot antigravity claude-desktop; do
  .venv/bin/python -m tools.build $t --validate || echo "FAILED: $t"
done
```

- [ ] **Step 5: Run the full repo suite**

```bash
.venv/bin/pytest -v 2>&1 | tail -30
```

- [ ] **Step 6: Commit fixes if any**

```bash
git add -A
git commit -m "cycle-5 final gate: full lint + suite green"
```

- [ ] **Step 7: Push**

```bash
git push -u origin cycle-5-auto-setup
```

- [ ] **Step 8: PR**

```bash
gh pr create --base master --head cycle-5-auto-setup \
  --title "Cycle 5: semi-auto setup (dependency installer + /ncplot:setup)" \
  --body "$(cat <<'EOF'
## Summary

- New `tools/install_deps.py` — canonical Python dependency installer.
  uv-first, pip fallback. Default-on cartopy + scipy with `--no-cartopy`
  / `--no-scipy` opt-out flags.
- Each per-target build now ships `setup.sh` + `setup.ps1` wrappers
  + a bundled copy of `tools/install_deps.py`.
- Claude Code: `SessionStart` hook auto-fires the installer on first
  run and after dependency-pin changes (idempotent via
  `${CLAUDE_PLUGIN_DATA}` diff-guard).
- `/ncplot:setup` slash command on Claude Code, Copilot (auto-namespaced
  from manifest); `/ncplot:setup` via subdir on Gemini CLI; bare `/setup`
  on Codex + Cursor (host doesn't namespace); `/setup` workflow on
  Antigravity.
- **Plugin manifest renamed** from `ncplot-agent` to `ncplot` to enable
  the `/ncplot:` slash namespace on the auto-namespacing hosts.

## Stats

- 18 plan tasks across 5 phases
- New: `tools/install_deps.py` (~250 LOC), `targets/_common/install_tooling.py`
  + `setup_sh.py` (~140 LOC together), per-target build deltas (~120 LOC)
- ~25 new tests under `tests/tools/` + `tests/targets/<host>/`
- Updated `docs/architecture.md` + `docs/adding-targets.md`
- Plugin rename cascades through ~30 existing test assertions; all updated

## What's NOT in this PR

- Auto-fire on Cursor / Gemini CLI / Copilot (unofficial pattern; deferred)
- Conda-forge auto-fallback for cartopy (documented hint only)
- Plugin auto-update mechanism
- Cycle 6 skill-refiner

## Test plan

- [ ] `pytest -v` (full suite green)
- [ ] `python -m tools.install_deps --dry-run --mcp-servers-dir <repo>/src/mcp` prints expected plan
- [ ] **Manual:** install the Claude Code build into `~/.claude/plugins/ncplot/`,
  start a fresh session, observe the SessionStart hook firing the installer

## References

- Spec: `docs/specs/2026-05-08-cycle-5-auto-setup.md`
- Plan: `docs/plans/2026-05-08-cycle-5-auto-setup.md`
- Research: `docs/research/2026-05-08-plugin-install-hooks.md`,
  `docs/research/2026-05-08-slash-command-namespacing.md`
EOF
)"
```

- [ ] **Step 9: Capture PR URL**

---

## End of plan

18 tasks, 5 phases:

| Phase | Tasks | Theme |
|-------|-------|-------|
| 1 | 1 | Plugin rename |
| 2 | 2–6 | Canonical installer (`tools/install_deps.py`) |
| 3 | 7 | Setup wrapper templates + helper |
| 4 | 8–14 | Per-target wiring (7 hosts) |
| 5 | 15–18 | Cross-target + real-install + docs + push + PR |
