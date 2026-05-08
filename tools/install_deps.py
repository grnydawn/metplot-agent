"""Cycle-5 canonical dependency installer for metplot.

Installs the two MCP server packages plus optional cartopy + scipy.
Used as: `python -m tools.install_deps [flags]` (from repo root) or
indirectly via the per-target `setup.sh` / `setup.ps1` wrappers
bundled in each plugin payload.

See docs/specs/2026-05-08-cycle-5-auto-setup.md for the full design.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
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
        prog="metplot-install",
        description="Install metplot's Python dependencies (cycle 5).",
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

    raise EnvironmentError_(
        f"No Python >= 3.10 found. Got {sys.version_info[:2]}; "
        "install Python 3.10+ from https://www.python.org/downloads/"
    )


def detect_installer(python_bin: Path) -> tuple[str, list[str]]:
    """Return (cmd, base_args) for the chosen package manager.

    Order:
      1. uv (if `uv` on PATH) -> ("uv", ["pip", "install"])
      2. pip via <python_bin> -m pip -> (str(python_bin), ["-m", "pip", "install"])
    """
    uv = shutil.which("uv")
    if uv:
        return ("uv", ["pip", "install"])
    return (str(python_bin), ["-m", "pip", "install"])


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


EXIT_OK = 0
EXIT_REQUIRED_FAILED = 1
EXIT_BAD_ENV = 2
EXIT_BAD_ARGS = 3


@dataclass
class _RunResult:
    """Stand-in for subprocess.run result when the call itself errored."""
    returncode: int
    stderr: str = ""


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

    _print(args, "metplot setup")
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

        result: subprocess.CompletedProcess[bytes] | _RunResult
        try:
            result = subprocess.run(cmd, check=False)
        except FileNotFoundError as e:
            result = _RunResult(returncode=127, stderr=str(e))

        if result.returncode == 0:
            _print(args, "      done")
            n_ok += 1
        elif step.required:
            print(f"      FAILED -- exit {result.returncode}", flush=True)
            print("      Required step. Aborting.", flush=True)
            return EXIT_REQUIRED_FAILED
        else:
            print(f"      FAILED -- exit {result.returncode}", flush=True)
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


if __name__ == "__main__":
    raise SystemExit(main())
