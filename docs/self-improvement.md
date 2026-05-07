# Self-improvement loop

## Premise

Hermes' learning loop (autonomous skill creation, in-use refinement, persistent
memory) is its main differentiator. Other agent hosts don't have it natively.
We want it, but with two adjustments for our use case:

1. **Reviewable.** Skills control what plots get produced from scientific data.
   A subtly wrong refinement compounds silently. Every change passes a human eye.
2. **Portable.** The refinement loop is implemented at the *skill* layer, not
   bolted into the agent runtime. That way it works the same everywhere.

## Components

```
┌──────────────────────────────────────────────────────────────────┐
│  During a session                                                 │
│                                                                   │
│  user task ──► skill executes ──► output                          │
│       │             │                                             │
│       │             └── notes + corrections + dead ends           │
│       │                                                           │
│       ▼                                                           │
│  task-log.jsonl   (one entry per significant step)                │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│  At end of session (auto via Stop hook, or manual /refine)        │
│                                                                   │
│  skill-refiner reads task-log.jsonl                               │
│      │                                                            │
│      ├── identifies: new aliases, pitfalls hit, user prefs        │
│      ├── locates: which canonical skill each lesson belongs in    │
│      └── writes: .ncplot/refinements/<timestamp>-<skill>.md       │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│  Out of band — user runs `ncplot-refine`                          │
│                                                                   │
│  shows diff of each draft refinement                              │
│  user accepts/edits/rejects                                       │
│  accepted patches merge into src/skills/                          │
│  next build distributes them to all targets                       │
└──────────────────────────────────────────────────────────────────┘
```

## What gets logged

The skills themselves write structured entries to `.ncplot/task-log.jsonl`
through a small helper exposed by the MCP servers (or written directly via the
agent's filesystem tool). Each entry:

```json
{
  "ts": "2026-05-06T14:30:00Z",
  "skill": "netcdf-plot-map",
  "step": "resolve_variable",
  "input": "user said: SST",
  "resolved": "tos",
  "via": "user_correction",
  "note": "CMIP6 file uses 'tos' not 'sst'"
}
```

Categories the refiner looks for:

| Tag             | Example                                            | Refines      |
|-----------------|----------------------------------------------------|--------------|
| `alias`         | "SST" → `tos` in CMIP6                             | `references/aliases.md` |
| `pitfall`       | longitude was 0–360 not -180–180                   | `Pitfalls` in SKILL.md |
| `user_pref`     | user prefers `viridis` over `RdYlBu_r` for SST     | `metadata.config` |
| `default`       | user always wants 1° box around storm centre       | `Quick Reference` in SKILL.md |
| `failure_mode`  | empty slice produced blank plot, no error          | `Verification` in SKILL.md |

## Refinement file format

Each draft refinement is a markdown file with a YAML header naming the target
skill and proposed edits. Example:

```markdown
---
target: src/skills/netcdf-plot-map/SKILL.md
section: Pitfalls
operation: append
confidence: high
evidence:
  - task-log entry at 2026-05-06T14:30:00Z
  - user said "no it's 0-360 in this file"
---
- WRF output uses 0–360 longitude convention. If user names a region with
  negative longitudes (e.g. "North Atlantic", -80–0), shift the data
  longitude axis or the region bounds before subsetting.
```

The `operation` is one of `append`, `replace_section`, `add_alias`,
`set_config_default`. The applier knows how to splice each kind into the
target file.

## Trigger options per target

- **Claude Code** — register a `Stop` hook that runs the refiner skill in a
  fresh subagent at session end. The hook is part of the built plugin.
- **Claude Desktop** — no hook system; user invokes `/refine` manually at
  end of session.
- **Codex** — manual; the AGENTS.md instructs the agent to consider invoking
  the refiner after multi-step plotting tasks.
- **Hermes** — Hermes' own learning loop will fire its `skill_manage` tool;
  the `skill-refiner` we ship is wired to write to the same `.ncplot/`
  refinement queue rather than directly modifying skills, so the human
  review step still happens.

## What this gets you that "just trust the agent" doesn't

1. **Auditable history.** Every refinement is a markdown file with evidence.
   Months later you can see why `tos` was added as an alias.
2. **Reversible.** Refinements live in git once accepted; revert with `git
   revert` if a bad pattern slips through review.
3. **Shareable.** Accepted refinements travel with the canonical skills.
   A team can converge on a shared skill set instead of every developer's
   agent learning the same lessons independently.
4. **Failure-resistant.** A wrong refinement doesn't immediately become
   active; it has to pass review. The cost of a typo or a misunderstanding
   is bounded.

## What this *doesn't* solve

- **Silent numerical errors** in plotting code itself (wrong projection math,
  off-by-one in indexing, unit-conversion bugs) — those need verification
  inside the MCP servers, not at the skill layer. See the Verification
  section in each plot skill for the lightweight checks we do at runtime
  (min/max/mean reporting, output-file size sanity, coordinate-axis
  monotonicity).
- **Concept drift.** If you change datasets or workflows fundamentally,
  refinements accumulated under the old regime may not apply. The
  `confidence` and `evidence` fields help spot stale patterns during review.

## Open questions

- Should we let the refiner propose *new skills*, not just edits to existing
  ones? Currently it only edits. Adding a skill is a bigger change and a
  bigger review burden; for now we leave it as a manual operation.
- Cross-skill conflicts. If two refinements target the same line in the
  same skill, the applier currently flags it for manual merge. A smarter
  three-way merge could help.
