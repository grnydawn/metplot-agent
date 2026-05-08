"""Review and apply skill refinements drafted by skill-refiner.

Reads drafts from .metplot/refinements/, shows each as a diff against its
target file, and lets the user accept / edit / reject. Accepted patches
merge into the canonical skill files in src/.

Operations supported:
- append              — add to the end of a named section
- replace_section     — replace the body of a named section
- add_alias           — structured insert into aliases.md table
- add_region          — structured insert into regions.md table
- set_config_default  — update YAML frontmatter config

Status: scaffold. The frontmatter parsing and the simpler operations
(append) are implemented; structured table edits and frontmatter edits
are TODO.

Usage:
    metplot-refine             # interactive review
    metplot-refine --list      # list pending refinements
    metplot-refine --apply <file>   # non-interactive apply (with confirm)
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import click
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
REFINEMENTS_DIR = Path.cwd() / ".metplot" / "refinements"
APPLIED_DIR = REFINEMENTS_DIR / "applied"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def parse_refinement(path: Path) -> dict:
    """Parse a refinement draft file into {meta, body}."""
    text = path.read_text()
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError(f"{path}: no YAML frontmatter")
    meta = yaml.safe_load(m.group(1)) or {}
    body = m.group(2).strip()
    return {"meta": meta, "body": body, "path": path}


def list_refinements() -> list[dict]:
    if not REFINEMENTS_DIR.exists():
        return []
    out = []
    for p in sorted(REFINEMENTS_DIR.glob("*.md")):
        try:
            out.append(parse_refinement(p))
        except (ValueError, yaml.YAMLError) as e:
            click.echo(click.style(f"  skipping {p.name}: {e}", fg="yellow"))
    return out


def apply_append(target: Path, section: str, body: str) -> str:
    """Append `body` to the end of the named section in `target`. Return preview."""
    text = target.read_text()
    # Find section header (## SectionName).
    pattern = re.compile(rf"^(##\s+{re.escape(section)}\s*\n)(.*?)(?=^##\s|\Z)", re.MULTILINE | re.DOTALL)
    m = pattern.search(text)
    if not m:
        raise ValueError(f"section '{section}' not found in {target}")
    new_section = m.group(0).rstrip() + "\n\n" + body.strip() + "\n\n"
    new_text = text[:m.start()] + new_section + text[m.end():]
    target.write_text(new_text)
    return new_section


def apply_refinement(ref: dict) -> None:
    meta = ref["meta"]
    body = ref["body"]
    target_rel = meta["target"]
    target = REPO_ROOT / target_rel
    if not target.exists():
        raise click.ClickException(f"target file does not exist: {target}")

    op = meta.get("operation", "append")
    section = meta.get("section")

    if op == "append":
        if not section:
            raise click.ClickException("append operation requires `section`")
        apply_append(target, section, body)
    elif op == "replace_section":
        # TODO
        raise click.ClickException("replace_section not implemented yet")
    elif op == "add_alias":
        # TODO: parse table row from body, splice into aliases.md
        raise click.ClickException("add_alias not implemented yet")
    elif op == "add_region":
        # TODO: parse region row, splice into regions.md AND regions.json
        raise click.ClickException("add_region not implemented yet")
    elif op == "set_config_default":
        # TODO: edit YAML frontmatter
        raise click.ClickException("set_config_default not implemented yet")
    else:
        raise click.ClickException(f"unknown operation: {op}")


def archive(ref: dict) -> None:
    APPLIED_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = APPLIED_DIR / f"{stamp}-{ref['path'].name}"
    shutil.move(str(ref["path"]), dest)


def render_summary(ref: dict) -> str:
    meta = ref["meta"]
    return (
        f"  target:     {meta.get('target', '?')}\n"
        f"  section:    {meta.get('section', '?')}\n"
        f"  operation:  {meta.get('operation', '?')}\n"
        f"  confidence: {meta.get('confidence', '?')}\n"
        f"  evidence:\n"
        + "\n".join(f"    - {e}" for e in meta.get("evidence", []))
    )


@click.command()
@click.option("--list", "list_", is_flag=True, help="List pending refinements and exit.")
@click.option("--apply", "apply_path", type=click.Path(exists=True, path_type=Path),
              help="Apply a single refinement file non-interactively (with confirmation).")
def cli(list_: bool, apply_path: Path | None) -> None:
    if list_:
        refs = list_refinements()
        if not refs:
            click.echo("no pending refinements")
            return
        for r in refs:
            click.echo(click.style(r["path"].name, bold=True))
            click.echo(render_summary(r))
            click.echo()
        return

    if apply_path:
        ref = parse_refinement(apply_path)
        click.echo(render_summary(ref))
        click.echo()
        click.echo("--- proposed body ---")
        click.echo(ref["body"])
        click.echo("--- end ---")
        if click.confirm("apply?"):
            apply_refinement(ref)
            archive(ref)
            click.echo(click.style("applied.", fg="green"))
        return

    refs = list_refinements()
    if not refs:
        click.echo("no pending refinements")
        return

    for r in refs:
        click.echo()
        click.echo(click.style(f"= {r['path'].name} =", bold=True))
        click.echo(render_summary(r))
        click.echo()
        click.echo("--- proposed body ---")
        click.echo(r["body"])
        click.echo("--- end ---")
        choice = click.prompt(
            "[a]ccept / [s]kip / [r]eject / [q]uit",
            default="s",
            show_choices=False,
        ).lower().strip()
        if choice in ("a", "accept"):
            try:
                apply_refinement(r)
                archive(r)
                click.echo(click.style("  applied.", fg="green"))
            except click.ClickException as e:
                click.echo(click.style(f"  error: {e.message}", fg="red"))
        elif choice in ("r", "reject"):
            r["path"].unlink()
            click.echo("  rejected (deleted).")
        elif choice in ("q", "quit"):
            click.echo("  quit.")
            return
        else:
            click.echo("  skipped.")


if __name__ == "__main__":
    cli()
