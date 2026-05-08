# Contributing

## Layout reminder

- `src/` is canonical. Edit skills, MCPs, and reference data here.
- `targets/` are build adapters. Edit only when adding a new agent host or
  fixing a target-specific quirk.
- `build/` is generated. Don't commit it (gitignored).
- `.metplot/` is per-user runtime state (task logs, refinement drafts).
  Don't commit.

## Adding a skill

```
mkdir -p src/skills/my-skill/references src/skills/my-skill/scripts
$EDITOR src/skills/my-skill/SKILL.md
```

Then run `python -m tools.lint_skills` to validate format. See an existing
skill (`netcdf-plot-map` is the most fleshed-out reference) for level of
detail expectations.

## Adding a target

See `docs/adding-targets.md`.

## Refinement workflow

1. Use the agent for real plotting work.
2. When the agent encounters a correction, log it via
   `.metplot/task-log.jsonl`.
3. At session end, invoke the `skill-refiner` skill (or rely on the Stop
   hook on Claude Code).
4. Run `metplot-refine` to review drafts under `.metplot/refinements/`.
5. Accept the keepers; commit the changes to `src/skills/`.

## Pre-commit checks

```
make lint
make test
```

PRs that touch `src/skills/` should include a brief note about whether the
change came from a refinement (and if so, link the original draft) or was
hand-written.
