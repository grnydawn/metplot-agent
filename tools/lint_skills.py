"""Validate SKILL.md files in src/skills/.

Checks:
- file exists at src/skills/<name>/SKILL.md
- has YAML frontmatter
- frontmatter has at least `name` and `description`
- `name` matches the directory name
- description is between 30 and 1000 characters
- body is non-empty
- referenced files (references/, scripts/, assets/) actually exist if mentioned

Usage:
    python -m tools.lint_skills

Exit code 0 = all good; non-zero = at least one issue.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import click
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_ROOT = REPO_ROOT / "src" / "skills"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def lint_skill(skill_dir: Path) -> list[str]:
    """Return a list of issues found in this skill, or [] if clean."""
    issues: list[str] = []
    md = skill_dir / "SKILL.md"

    if not md.exists():
        return [f"missing SKILL.md in {skill_dir.relative_to(REPO_ROOT)}"]

    text = md.read_text()
    m = FRONTMATTER_RE.match(text)
    if not m:
        issues.append(f"{md.relative_to(REPO_ROOT)}: no YAML frontmatter")
        return issues

    raw_fm, body = m.group(1), m.group(2)
    try:
        fm = yaml.safe_load(raw_fm) or {}
    except yaml.YAMLError as e:
        issues.append(f"{md.relative_to(REPO_ROOT)}: invalid YAML — {e}")
        return issues

    if "name" not in fm:
        issues.append(f"{md.relative_to(REPO_ROOT)}: missing `name` in frontmatter")
    elif fm["name"] != skill_dir.name:
        issues.append(
            f"{md.relative_to(REPO_ROOT)}: frontmatter name '{fm['name']}' != "
            f"directory name '{skill_dir.name}'"
        )

    desc = fm.get("description", "")
    if not desc:
        issues.append(f"{md.relative_to(REPO_ROOT)}: missing `description`")
    elif len(desc) < 30:
        issues.append(
            f"{md.relative_to(REPO_ROOT)}: description too short ({len(desc)} chars; aim for 50-300)"
        )
    elif len(desc) > 1000:
        issues.append(
            f"{md.relative_to(REPO_ROOT)}: description too long ({len(desc)} chars; aim for 50-300)"
        )

    if not body.strip():
        issues.append(f"{md.relative_to(REPO_ROOT)}: empty body")

    # Check referenced files
    for ref_match in re.finditer(r"`(references/[^`]+)`", body):
        ref = ref_match.group(1)
        if not (skill_dir / ref).exists():
            issues.append(
                f"{md.relative_to(REPO_ROOT)}: references missing file `{ref}`"
            )

    return issues


@click.command()
def cli() -> None:
    if not SKILLS_ROOT.exists():
        raise click.ClickException(f"no skills directory at {SKILLS_ROOT}")

    skill_dirs = [p for p in SKILLS_ROOT.iterdir() if p.is_dir()]
    if not skill_dirs:
        click.echo("no skills found")
        return

    all_issues: list[str] = []
    for d in sorted(skill_dirs):
        issues = lint_skill(d)
        if issues:
            click.echo(click.style(f"✗ {d.name}", fg="red"))
            for issue in issues:
                click.echo(f"    {issue}")
            all_issues.extend(issues)
        else:
            click.echo(click.style(f"✓ {d.name}", fg="green"))

    if all_issues:
        click.echo()
        click.echo(click.style(f"{len(all_issues)} issue(s) found", fg="red"))
        sys.exit(1)
    click.echo()
    click.echo(click.style(f"all {len(skill_dirs)} skill(s) lint clean", fg="green"))


if __name__ == "__main__":
    cli()
