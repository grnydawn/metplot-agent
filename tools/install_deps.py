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
