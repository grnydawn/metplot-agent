# tests/tools/test_apply_refinements.py
"""Cycle-6 Phase B contract: skill-refiner draft refinements can be
applied to canonical skill files via `metplot-refine`.

One TestClass per implemented op (per spec §3.3). Phase A sign-off
justified three ops:

  - add_alias           — 3 alias findings
  - replace_section     — 5+ pitfall findings + 2 partial-fix
                          failure_mode findings naming Pitfalls edits
  - set_config_default  — 2 findings (TEOS-10 surface-layer default,
                          precip-units conversion default)

The fourth op, add_region, had ZERO Phase A findings — the stubbed
ClickException is the contract until a future cycle's Phase A
justifies the implementation cost. `TestAddRegionStaysStubbed`
locks that contract in.

Fixtures live under `tests/tools/fixtures/refinements/`. Each
fixture is derived from a real Phase A finding so the tests
double as integration coverage on the refinements that actually
shipped."""
from __future__ import annotations

from pathlib import Path

import click
import pytest

from tools.apply_refinements import (
    apply_add_alias,
    apply_refinement,
    apply_replace_section,
    apply_set_config_default,
    parse_refinement,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "refinements"


def _ref(name: str) -> dict:
    return parse_refinement(FIXTURES_DIR / name)


def _aliases_target(p: Path) -> Path:
    """Construct a minimal aliases.md-style file with splice markers
    at `p`, returning the path. Mirrors the real shape of
    `src/skills/netcdf-inspect/references/aliases.md`."""
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "# Variable aliases\n"
        "\n"
        "## Sea surface temperature\n"
        "\n"
        "| User says | Possible variable names | Notes |\n"
        "|-----------|-------------------------|-------|\n"
        "| SST | `sst`, `tos` | |\n"
        "\n"
        "## Dataset-specific quirks\n"
        "\n"
        "<!-- REFINER_INSERT_BELOW -->\n"
        "<!-- New entries from skill-refiner are appended below. -->\n"
        "\n"
        "<!-- REFINER_INSERT_ABOVE -->\n"
        "\n"
        "## Adding entries manually\n"
        "\n"
        "Format: a short table row under the appropriate section.\n"
    )
    return p


def _skill_md_target(p: Path) -> Path:
    """Construct a minimal SKILL.md-style file with frontmatter and
    a Pitfalls section."""
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "---\n"
        "name: test-skill\n"
        "description: A test skill.\n"
        "---\n"
        "\n"
        "# Test skill\n"
        "\n"
        "## When to use\n"
        "\n"
        "Whenever.\n"
        "\n"
        "## Pitfalls\n"
        "\n"
        "- Watch out for X.\n"
        "- Watch out for Y.\n"
        "\n"
        "## See also\n"
        "\n"
        "- nothing\n"
    )
    return p


class TestAddAlias:
    """add_alias: splice fixture body between aliases.md markers."""

    def test_splices_body_between_markers(self, tmp_path: Path) -> None:
        target = _aliases_target(
            tmp_path / "src/skills/netcdf-inspect/references/aliases.md")
        ref = _ref("20260511-add-alias-teos10.md")
        apply_refinement(ref, repo_root=tmp_path)
        new_text = target.read_text()
        # Body landed between the markers.
        below = new_text.index("<!-- REFINER_INSERT_BELOW -->")
        above = new_text.index("<!-- REFINER_INSERT_ABOVE -->")
        assert below < new_text.index("MPAS-Ocean") < above

    def test_preserves_content_outside_markers(self, tmp_path: Path) -> None:
        """Adding an alias must NOT touch other sections — spec §4.7
        'Applier never silently desyncs.'"""
        target = _aliases_target(
            tmp_path / "src/skills/netcdf-inspect/references/aliases.md")
        ref = _ref("20260511-add-alias-teos10.md")
        original = target.read_text()
        apply_refinement(ref, repo_root=tmp_path)
        new_text = target.read_text()
        # "Sea surface temperature" section untouched.
        assert "## Sea surface temperature" in new_text
        assert "## Adding entries manually" in new_text
        # Original header line unchanged.
        assert original.split("\n", 1)[0] == new_text.split("\n", 1)[0]

    def test_refuses_when_markers_absent(self, tmp_path: Path) -> None:
        """A file without splice markers can't safely accept this
        op — refusing is the right move, not falling back to append."""
        target = tmp_path / "src/skills/netcdf-inspect/references/aliases.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# aliases (no markers here)\n")
        with pytest.raises(click.ClickException) as exc:
            apply_add_alias(target, "## new section\n\n| row |\n")
        assert "splice marker" in str(exc.value.message).lower()

    def test_refuses_when_marker_duplicated(self, tmp_path: Path) -> None:
        """Two BELOW markers means ambiguity — refuse."""
        target = tmp_path / "aliases.md"
        target.write_text(
            "<!-- REFINER_INSERT_BELOW -->\n"
            "first\n"
            "<!-- REFINER_INSERT_ABOVE -->\n"
            "<!-- REFINER_INSERT_BELOW -->\n"
            "second\n"
            "<!-- REFINER_INSERT_ABOVE -->\n"
        )
        with pytest.raises(click.ClickException) as exc:
            apply_add_alias(target, "new body")
        msg = str(exc.value.message).lower()
        assert "exactly one" in msg or "splice marker" in msg

    def test_refuses_when_markers_in_wrong_order(self, tmp_path: Path) -> None:
        target = tmp_path / "aliases.md"
        target.write_text(
            "<!-- REFINER_INSERT_ABOVE -->\n"
            "between\n"
            "<!-- REFINER_INSERT_BELOW -->\n"
        )
        with pytest.raises(click.ClickException) as exc:
            apply_add_alias(target, "new body")
        assert "wrong order" in str(exc.value.message).lower()

    def test_write_is_atomic_no_tmp_leftover(
        self, tmp_path: Path,
    ) -> None:
        """The atomic-rename write helper should leave no `*.md.tmp`
        sibling after success."""
        target = _aliases_target(
            tmp_path / "src/skills/netcdf-inspect/references/aliases.md")
        ref = _ref("20260511-add-alias-teos10.md")
        apply_refinement(ref, repo_root=tmp_path)
        leftover = list(target.parent.glob("*.tmp"))
        assert leftover == [], f"tmp files left over: {leftover}"


class TestReplaceSection:
    """replace_section: replace `## SectionName` body wholesale."""

    def test_replaces_pitfalls_with_fixture_body(
        self, tmp_path: Path,
    ) -> None:
        target = _skill_md_target(
            tmp_path / "src/skills/netcdf-inspect/SKILL.md")
        ref = _ref("20260511-replace-section-pitfalls-mpas-pairing.md")
        apply_refinement(ref, repo_root=tmp_path)
        new_text = target.read_text()
        # Old Pitfalls body gone.
        assert "Watch out for X" not in new_text
        assert "Watch out for Y" not in new_text
        # New body present.
        assert "MPAS mesh-history pairing" in new_text
        assert "Restart files are not history files" in new_text
        assert "Dual-grid files" in new_text

    def test_keeps_section_header(self, tmp_path: Path) -> None:
        """The `## Pitfalls` header itself must survive — only the
        body changes."""
        target = _skill_md_target(
            tmp_path / "src/skills/netcdf-inspect/SKILL.md")
        ref = _ref("20260511-replace-section-pitfalls-mpas-pairing.md")
        apply_refinement(ref, repo_root=tmp_path)
        assert "## Pitfalls" in target.read_text()

    def test_preserves_other_sections(self, tmp_path: Path) -> None:
        target = _skill_md_target(
            tmp_path / "src/skills/netcdf-inspect/SKILL.md")
        ref = _ref("20260511-replace-section-pitfalls-mpas-pairing.md")
        apply_refinement(ref, repo_root=tmp_path)
        new_text = target.read_text()
        # When-to-use section untouched.
        assert "## When to use" in new_text
        assert "Whenever." in new_text
        # See-also section untouched.
        assert "## See also" in new_text

    def test_preserves_frontmatter(self, tmp_path: Path) -> None:
        target = _skill_md_target(
            tmp_path / "src/skills/netcdf-inspect/SKILL.md")
        ref = _ref("20260511-replace-section-pitfalls-mpas-pairing.md")
        apply_refinement(ref, repo_root=tmp_path)
        new_text = target.read_text()
        assert new_text.startswith("---\nname: test-skill\n")

    def test_refuses_when_section_absent(self, tmp_path: Path) -> None:
        target = _skill_md_target(tmp_path / "skill.md")
        with pytest.raises(click.ClickException) as exc:
            apply_replace_section(target, "NoSuchSection", "new body")
        assert "not found" in str(exc.value.message).lower()


class TestSetConfigDefault:
    """set_config_default: round-trip YAML frontmatter `key: value` edit."""

    def test_adds_new_key_to_frontmatter(self, tmp_path: Path) -> None:
        target = _skill_md_target(
            tmp_path / "src/skills/netcdf-plot-map/SKILL.md")
        ref = _ref("20260511-set-config-default-surface-layer.md")
        apply_refinement(ref, repo_root=tmp_path)
        new_text = target.read_text()
        assert "surface_layer_default: top" in new_text

    def test_preserves_existing_frontmatter_keys(
        self, tmp_path: Path,
    ) -> None:
        target = _skill_md_target(
            tmp_path / "src/skills/netcdf-plot-map/SKILL.md")
        ref = _ref("20260511-set-config-default-surface-layer.md")
        apply_refinement(ref, repo_root=tmp_path)
        new_text = target.read_text()
        # name + description survive.
        assert "name: test-skill" in new_text
        assert "description: A test skill." in new_text

    def test_overwrites_existing_key(self, tmp_path: Path) -> None:
        target = _skill_md_target(tmp_path / "skill.md")
        # First write — key absent, gets added.
        apply_set_config_default(target, "key_x", "first")
        assert "key_x: first" in target.read_text()
        # Second write — key present, gets overwritten.
        apply_set_config_default(target, "key_x", "second")
        text = target.read_text()
        assert "key_x: second" in text
        assert "key_x: first" not in text

    def test_preserves_body_verbatim(self, tmp_path: Path) -> None:
        """Spec §4 principle 5: 'Body content preserved verbatim.'"""
        target = _skill_md_target(tmp_path / "skill.md")
        original_body = target.read_text().split("---\n", 2)[2]
        apply_set_config_default(target, "new_key", "new_value")
        new_body = target.read_text().split("---\n", 2)[2]
        assert new_body == original_body

    def test_refuses_when_no_frontmatter(self, tmp_path: Path) -> None:
        target = tmp_path / "no-frontmatter.md"
        target.write_text("# heading\n\nplain body\n")
        with pytest.raises(click.ClickException) as exc:
            apply_set_config_default(target, "k", "v")
        assert "frontmatter" in str(exc.value.message).lower()

    def test_refuses_when_frontmatter_malformed(
        self, tmp_path: Path,
    ) -> None:
        target = tmp_path / "bad.md"
        target.write_text("---\nname: : : bad : yaml\n---\nbody\n")
        with pytest.raises(click.ClickException) as exc:
            apply_set_config_default(target, "k", "v")
        msg = str(exc.value.message).lower()
        assert "yaml" in msg or "parse" in msg

    def test_round_trip_via_safe_load(self, tmp_path: Path) -> None:
        """After write, the new frontmatter must parse back via
        yaml.safe_load — guards against any safe_dump emitting
        non-round-trippable output."""
        import yaml
        target = _skill_md_target(tmp_path / "skill.md")
        apply_set_config_default(target, "new_key", "new_value")
        text = target.read_text()
        # Extract frontmatter and re-parse.
        from tools.apply_refinements import FRONTMATTER_RE
        m = FRONTMATTER_RE.match(text)
        assert m is not None
        fm = yaml.safe_load(m.group(1))
        assert fm["new_key"] == "new_value"
        assert fm["name"] == "test-skill"


class TestAddRegionStaysStubbed:
    """Phase A surfaced zero region findings. Spec §3.1 says ops with
    zero Phase-A evidence keep their ClickException body, with the
    message updated to name the cycle that should complete them."""

    def test_raises_actionable_clickexception(
        self, tmp_path: Path,
    ) -> None:
        target = tmp_path / "regions.md"
        target.write_text("# regions\n")
        # Hand-craft a minimal add_region ref since no fixture is
        # justified (zero Phase A evidence).
        ref = {
            "meta": {
                "target": "regions.md",
                "operation": "add_region",
            },
            "body": "irrelevant",
            "path": tmp_path / "fake.md",
        }
        with pytest.raises(click.ClickException) as exc:
            apply_refinement(ref, repo_root=tmp_path)
        msg = str(exc.value.message).lower()
        # Must be an *informative* not-yet-implemented message, not a
        # bare TODO — the user reading the error needs to know why.
        assert "not implemented" in msg or "stubbed" in msg
        assert "phase a" in msg or "cycle" in msg, (
            f"add_region stub message must explain why it's deferred; "
            f"got: {exc.value.message!r}")


class TestUnknownOperationStillRejected:
    """Defensive: bad `operation` value in a draft is the user's
    or the refiner skill's fault; surface it cleanly."""

    def test_unknown_op_raises(self, tmp_path: Path) -> None:
        target = tmp_path / "x.md"
        target.write_text("body\n")
        ref = {
            "meta": {"target": "x.md", "operation": "frobulate"},
            "body": "...",
            "path": tmp_path / "fake.md",
        }
        with pytest.raises(click.ClickException) as exc:
            apply_refinement(ref, repo_root=tmp_path)
        assert "frobulate" in str(exc.value.message)


class TestFixturesAllParseCleanly:
    """Sanity: every fixture file we ship is a well-formed
    refinement draft. This guards against later edits silently
    breaking a fixture's frontmatter."""

    @pytest.mark.parametrize("fixture", sorted(FIXTURES_DIR.glob("*.md")),
                             ids=lambda p: p.name)
    def test_fixture_parses(self, fixture: Path) -> None:
        ref = parse_refinement(fixture)
        assert "target" in ref["meta"]
        assert "operation" in ref["meta"]
        assert ref["meta"]["operation"] in {
            "add_alias", "replace_section", "set_config_default"}
