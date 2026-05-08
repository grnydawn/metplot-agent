---
name: skill-refiner
description: Review a completed plotting session and propose patches to the canonical skills based on what was learned — new variable aliases, pitfalls hit, user preferences, regions defined. Use this at the end of a session that involved corrections, surprises, or new patterns the user wants captured. Also invoke when the user explicitly says "remember this", "update the skill", or "add this to the regions list". Writes draft refinements to .metplot/refinements/ for human review; does NOT modify canonical skills directly.
---

# skill-refiner

This is the closed-loop learning component. It brings Hermes-style
self-improvement to the plugin while keeping every change human-reviewed.

## When to use

- End of a session that involved corrections, surprises, or non-trivial
  problem solving.
- User explicitly says "remember this", "update the skill", "add this
  region", "next time use viridis for SST".
- After a multi-step plotting task (3+ tool calls) that succeeded.

Do NOT invoke for simple successful tasks — the noise in the refinement
queue makes review tedious. The threshold is: did anything happen this
session that wasn't already captured by the existing skills?

## Procedure

### 1. Read the task log

Open `.metplot/task-log.jsonl` (or read the conversation history if no
task log exists). Filter to entries from the current session.

### 2. Categorize observations

Walk through entries and tag each with one of:

| Tag             | What it means                                      | Refines              |
|-----------------|----------------------------------------------------|----------------------|
| `alias`         | User used name X, file used name Y                 | aliases.md           |
| `region`        | User named a region not in the list, gave bounds   | regions.md           |
| `pitfall`       | Something went wrong + we figured out why          | SKILL.md Pitfalls    |
| `user_pref`     | User overrode a default in a way they're likely to want again | SKILL.md / config |
| `failure_mode`  | Plot looked wrong even though no error fired       | SKILL.md Verification|
| `default`       | User repeatedly chose the same non-default option  | SKILL.md Quick Reference |

Skip anything already documented. A "lesson" the skill already
predicts is not a refinement.

### 3. Locate the right skill

Each observation maps to a target file:

- `alias` → `src/skills/netcdf-inspect/references/aliases.md`
- `region` → `src/skills/netcdf-plot-map/references/regions.md`
- `pitfall`, `user_pref`, `failure_mode`, `default` → the `SKILL.md` of
  whichever skill was active when the observation was logged

### 4. Draft the patch

Write a markdown file under `.metplot/refinements/` named
`<YYYYMMDD-HHMMSS>-<target-skill>-<short-tag>.md`. Format:

```markdown
---
target: src/skills/netcdf-plot-map/SKILL.md
section: Pitfalls
operation: append
confidence: high
evidence:
  - task-log entry at 2026-05-06T14:30:00Z
  - user message: "no it's 0-360 in this file"
  - context: WRF output, North Atlantic plot
---

## Proposed addition

- WRF output uses 0–360 longitude convention. Region bounds for
  Atlantic-centered regions need shifting before subsetting, otherwise
  the slice is empty and the plot is blank with no error.
```

Operations:
- `append` — add to the end of the section
- `replace_section` — replace a whole section (rare; needs strong evidence)
- `add_alias` — structured edit for the aliases table
- `add_region` — structured edit for the regions table
- `set_config_default` — change a config default in YAML frontmatter

### 5. Confidence rating

- `high` — explicit user statement ("always do X"), clear correction,
  reproducible failure.
- `medium` — observed once, plausible generalization but not confirmed.
- `low` — speculative; might be a one-off.

The reviewer (the human) sees confidence and uses it to triage. Default
to `medium` unless there's clear signal.

### 6. Don't propose changes the user didn't sanction

This is a standard you should hold tightly. If the user did something
once and didn't say "remember this", don't promote it to a default.
A skill that quietly drifts toward one user's idiosyncratic preferences
becomes useless to anyone else.

The bar for `default` and `user_pref` refinements is *explicit* user
expression of an ongoing preference, not just a single instance.

### 7. Tell the user what you wrote

After drafting refinements, summarize:

> Wrote 2 refinements to .metplot/refinements/:
> - `20260506-143012-netcdf-plot-map-pitfalls.md` (high confidence) —
>   WRF longitude convention pitfall
> - `20260506-143012-netcdf-inspect-aliases.md` (high confidence) —
>   "SST" → `tos` for CMIP6 files
>
> Run `metplot-refine` to review and apply.

## Pitfalls

- **Don't write to canonical skills.** Only `.metplot/refinements/`.
  The canonical files are git-tracked; modifications go through review.
- **Don't propose duplicates.** Read existing refinements in the queue
  and merge rather than creating a new file for the same observation.
- **Don't touch other skills' refinements.** Each refinement has a
  single `target` file. Don't write multi-target refinements.
- **Don't refine yourself.** This skill should not propose changes to
  `skill-refiner/SKILL.md`. Meta-loops compound errors fast.

## Verification

- Each draft refinement has valid YAML frontmatter (`target`, `section`,
  `operation`, `confidence`, `evidence`).
- Each `target` path exists.
- Each draft is under 100 lines (long refinements are usually two
  refinements stuck together — split them).

## How the apply step works

Out of band, the user runs `python -m tools.apply_refinements`. That
script:

1. Lists all drafts in `.metplot/refinements/`.
2. For each, shows the proposed diff against the target file.
3. User accepts, edits, or rejects.
4. Accepted drafts are merged into the canonical file via the operation
   semantics (append / replace_section / add_alias / etc.).
5. Applied drafts move to `.metplot/refinements/applied/` for audit history.

The refiner skill itself never runs the apply step — that's a deliberate
separation. Drafts are cheap; commits to canonical skills are deliberate.

## See also

- `docs/self-improvement.md` — design rationale
- `tools/apply_refinements.py` — the apply-step CLI
- `scripts/refine.py` — helper utilities for parsing the task log
