from pathlib import Path


def test_project_instructions_present(built_plugin: Path):
    assert (built_plugin / "project_instructions.md").is_file()


def test_concatenates_all_6_skills(built_plugin: Path):
    text = (built_plugin / "project_instructions.md").read_text()
    for name in ("netcdf-inspect", "netcdf-plot-router",
                  "netcdf-plot-map", "netcdf-plot-timeseries",
                  "netcdf-plot-profile", "skill-refiner"):
        assert f"## Skill: {name}" in text, f"missing skill section for {name}"


def test_skill_refiner_included(built_plugin: Path):
    text = (built_plugin / "project_instructions.md").read_text()
    assert "## Skill: skill-refiner" in text


def test_yaml_frontmatter_stripped(built_plugin: Path):
    """Concatenated bodies should not have raw YAML frontmatter blocks."""
    text = (built_plugin / "project_instructions.md").read_text()
    # The doc starts with markdown header, not "---\nname:". Search for any
    # appearances of "name: netcdf-" that would indicate unstripped FM.
    assert "name: netcdf-inspect\n" not in text
