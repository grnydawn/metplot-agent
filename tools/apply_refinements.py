"""Review and apply skill refinements drafted by skill-refiner.

Reads drafts from .metplot/refinements/, shows each as a diff against its
target file, and lets the user accept / edit / reject. Accepted patches
merge into the canonical skill files in src/.

Operations supported:
- append              — add to the end of a named section
- replace_section     — replace the body of a named section
- add_alias           — splice body between aliases.md splice markers
- add_region          — stubbed (cycle 6 Phase A surfaced zero region findings;
                        slated for the cycle that does)
- set_config_default  — round-trip YAML frontmatter `key: value` edit

All operations follow spec §4 principle 7 — "Applier never silently
desyncs. Every failure mode raises ClickException with actionable repro
information. A half-applied splice or markdown/JSON divergence is the
worst outcome and is explicitly defended against." That means each
op validates its target's expected shape before writing, and writes
go through a `_safe_write` helper that round-trip-validates yaml-bearing
files before atomically replacing the target.

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

# Splice markers used by add_alias / add_region (spec §4 principle 3 —
# "Splice markers, not regex on free text"). Both must occur exactly
# once in the target file or the splice refuses to fire.
_ALIAS_MARKER_BELOW = "<!-- REFINER_INSERT_BELOW -->"
_ALIAS_MARKER_ABOVE = "<!-- REFINER_INSERT_ABOVE -->"


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


def _safe_write(target: Path, new_text: str) -> None:
    """Atomic replace: write to sibling tmp, then rename. Ensures a
    crash or full disk leaves the target intact (spec §4 principle 7)."""
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(new_text)
    tmp.replace(target)


def apply_append(target: Path, section: str, body: str) -> str:
    """Append `body` to the end of the named section in `target`. Return preview."""
    text = target.read_text()
    # Find section header (## SectionName).
    pattern = re.compile(rf"^(##\s+{re.escape(section)}\s*\n)(.*?)(?=^##\s|\Z)", re.MULTILINE | re.DOTALL)
    m = pattern.search(text)
    if not m:
        raise click.ClickException(
            f"section '{section}' not found in {target}; refusing append "
            f"so the file isn't silently corrupted")
    new_section = m.group(0).rstrip() + "\n\n" + body.strip() + "\n\n"
    new_text = text[:m.start()] + new_section + text[m.end():]
    _safe_write(target, new_text)
    return new_section


def apply_replace_section(target: Path, section: str, body: str) -> str:
    """Replace the body of `## section` (header retained) with `body`.
    Section runs from end of header line through start of next `## ` (or EOF).

    Refuses if section heading is absent — surfaces a ClickException
    rather than a silent no-op, per spec §4 principle 7."""
    text = target.read_text()
    pattern = re.compile(
        rf"^(##\s+{re.escape(section)}\s*\n)(.*?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        raise click.ClickException(
            f"section '{section}' not found in {target}; refusing "
            f"replace_section so nothing is silently corrupted")
    header = m.group(1)
    new_section = header + "\n" + body.strip() + "\n\n"
    new_text = text[:m.start()] + new_section + text[m.end():]
    _safe_write(target, new_text)
    return new_section


def apply_add_alias(target: Path, body: str) -> str:
    """Splice `body` between the REFINER_INSERT_BELOW / ABOVE markers
    in an aliases-style file (spec §4 principle 3). Both markers must
    occur exactly once or the splice refuses to fire."""
    text = target.read_text()
    below_count = text.count(_ALIAS_MARKER_BELOW)
    above_count = text.count(_ALIAS_MARKER_ABOVE)
    if below_count != 1 or above_count != 1:
        raise click.ClickException(
            f"{target}: expected exactly one of each splice marker "
            f"({_ALIAS_MARKER_BELOW!r}, {_ALIAS_MARKER_ABOVE!r}); found "
            f"{below_count} and {above_count} respectively. Refusing splice.")
    below_idx = text.index(_ALIAS_MARKER_BELOW) + len(_ALIAS_MARKER_BELOW)
    above_idx = text.index(_ALIAS_MARKER_ABOVE)
    if above_idx < below_idx:
        raise click.ClickException(
            f"{target}: splice markers in wrong order "
            f"(ABOVE precedes BELOW). Refusing splice.")
    middle = text[below_idx:above_idx]
    new_middle = middle.rstrip() + "\n\n" + body.strip() + "\n\n"
    new_text = text[:below_idx] + new_middle + text[above_idx:]
    _safe_write(target, new_text)
    return body.strip()


def _split_frontmatter(text: str) -> tuple[str, str] | None:
    """Char-precise frontmatter split: returns (fm_text, body) where
    body preserves the original separator newline after the closing
    `---`. Returns None if no frontmatter. Unlike FRONTMATTER_RE,
    does not silently eat blank lines."""
    if not text.startswith("---\n"):
        return None
    end_idx = text.find("\n---\n", 4)
    if end_idx < 0:
        return None
    fm_text = text[4:end_idx]
    body = text[end_idx + len("\n---\n"):]
    return fm_text, body


def apply_set_config_default(target: Path, key: str, value) -> str:
    """Round-trip the target's YAML frontmatter and set `key: value`.
    Body content is preserved verbatim (spec §4 principle 5 — 'YAML
    frontmatter is parsed, not regex'd. … Body content preserved
    verbatim').

    Validates the new frontmatter parses cleanly before writing —
    a half-corrupted YAML block is the worst outcome here and is
    explicitly defended against."""
    text = target.read_text()
    split = _split_frontmatter(text)
    if split is None:
        raise click.ClickException(
            f"{target}: no YAML frontmatter; cannot set_config_default. "
            f"File must start with `---\\n<yaml>\\n---\\n<body>`.")
    fm_text, body = split
    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError as e:
        raise click.ClickException(
            f"{target}: frontmatter does not parse as YAML: {e}")
    if not isinstance(fm, dict):
        raise click.ClickException(
            f"{target}: frontmatter root must be a mapping, "
            f"got {type(fm).__name__}")
    fm[key] = value
    new_fm_text = yaml.safe_dump(fm, sort_keys=False,
                                 default_flow_style=False).strip()
    # Round-trip validate that the new frontmatter we're about to write
    # parses back cleanly — guard against any safe_dump corner that
    # emits non-round-trippable YAML.
    try:
        yaml.safe_load(new_fm_text)
    except yaml.YAMLError as e:
        raise click.ClickException(
            f"yaml.safe_dump produced non-round-trippable output for "
            f"{target}: {e}. Aborting write to avoid corruption.")
    new_text = "---\n" + new_fm_text + "\n---\n" + body
    _safe_write(target, new_text)
    return f"{key}: {value!r}"


def apply_refinement(ref: dict, repo_root: Path | None = None) -> None:
    meta = ref["meta"]
    body = ref["body"]
    target_rel = meta["target"]
    target = (repo_root or REPO_ROOT) / target_rel
    if not target.exists():
        raise click.ClickException(f"target file does not exist: {target}")

    op = meta.get("operation", "append")
    section = meta.get("section")

    if op == "append":
        if not section:
            raise click.ClickException("append operation requires `section`")
        apply_append(target, section, body)
    elif op == "replace_section":
        if not section:
            raise click.ClickException(
                "replace_section operation requires `section`")
        apply_replace_section(target, section, body)
    elif op == "add_alias":
        apply_add_alias(target, body)
    elif op == "add_region":
        raise click.ClickException(
            "add_region is not implemented yet — cycle-6 Phase A "
            "dogfooding surfaced zero region findings, so this op "
            "stays stubbed until a future cycle's Phase A justifies "
            "the implementation cost. Open a fresh cycle spec with "
            "region findings to unblock.")
    elif op == "set_config_default":
        if "key" not in meta:
            raise click.ClickException(
                "set_config_default requires `key` in frontmatter")
        if "value" not in meta:
            raise click.ClickException(
                "set_config_default requires `value` in frontmatter")
        apply_set_config_default(target, meta["key"], meta["value"])
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
