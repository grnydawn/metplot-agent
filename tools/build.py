"""Build dispatcher.

Usage:
    python -m tools.build <target>
    python -m tools.build --all
    python -m tools.build --list

Each target is a directory under `targets/` with a `build.py` that exposes
`build(src_root: Path, out_root: Path) -> None`.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import click

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
TARGETS_ROOT = REPO_ROOT / "targets"
BUILD_ROOT = REPO_ROOT / "build"


def discover_targets() -> dict[str, Path]:
    """Find all target directories that contain a build.py."""
    targets = {}
    if not TARGETS_ROOT.exists():
        return targets
    for path in TARGETS_ROOT.iterdir():
        if path.is_dir() and (path / "build.py").exists():
            targets[path.name] = path / "build.py"
    return targets


def load_target_module(name: str, build_py: Path):
    spec = importlib.util.spec_from_file_location(f"targets.{name}", build_py)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {build_py}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_target(name: str) -> None:
    targets = discover_targets()
    if name not in targets:
        available = ", ".join(sorted(targets)) or "(none)"
        raise click.ClickException(f"unknown target '{name}'. Available: {available}")
    out_dir = BUILD_ROOT / name
    out_dir.mkdir(parents=True, exist_ok=True)
    module = load_target_module(name, targets[name])
    if not hasattr(module, "build"):
        raise click.ClickException(f"{targets[name]} does not export build()")
    click.echo(f"building {name} → {out_dir.relative_to(REPO_ROOT)}")
    module.build(SRC_ROOT, out_dir)
    click.echo(f"  done.")


@click.command()
@click.argument("target", required=False)
@click.option("--all", "all_", is_flag=True, help="Build every registered target.")
@click.option("--list", "list_", is_flag=True, help="List available targets and exit.")
def cli(target: str | None, all_: bool, list_: bool) -> None:
    targets = discover_targets()
    if list_:
        if not targets:
            click.echo("no targets registered")
            return
        for name in sorted(targets):
            click.echo(name)
        return
    if all_:
        if not targets:
            raise click.ClickException("no targets registered")
        for name in sorted(targets):
            build_target(name)
        return
    if not target:
        raise click.ClickException("specify a target, --all, or --list")
    build_target(target)


if __name__ == "__main__":
    cli()
