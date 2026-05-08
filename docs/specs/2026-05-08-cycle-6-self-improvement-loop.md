# Cycle 6 — Self-improvement loop

> Spec for the closed-loop learning layer: skill-refiner shipping in
> built plugins, real `/refine` slash command + `Stop` hook on Claude
> Code, applier CLI completed for the operations dogfood evidence
> justifies, and other-host placeholders rewritten to reflect the
> now-shipping skill.
>
> Deferred from cycles 4–5–7 ("hooks + skill-refiner stay deferred to
> cycle 6"). Reshaped from an earlier strawman after dogfood evidence
> made the per-host wiring scope and applier op set narrower.

## 0. Why this spec is shaped this way

The cycles before this one shipped the canonical skills (cycle 3), the
target builds (cycles 4 + 7), and semi-auto setup (cycle 5). At each
point the closed-loop learning component — the `skill-refiner` skill
plus its per-host triggers and applier CLI — got deliberately deferred
to "cycle 6." That accumulated backlog motivated the strawman scope.

But the strawman committed to building the entire matrix in a single
cycle: real `/refine` on five hosts, `Stop` hook on Claude Code, all
four applier operations completed, plus docs. Approximately 17 tasks
of speculatively-useful work — same sizing as cycle 5 / 7, none of it
validated against real session evidence.

This cycle therefore has two phases. Phase A produces evidence; Phase
B builds against it. The phases ship in order; the spec at the end of
Phase A may differ from the spec at the start of Phase A. This file is
the start-of-Phase-A version. If Phase A surfaces something that
contradicts these requirements, this file gets rewritten before Phase
B begins; the rewrite happens as a normal commit so the diff is visible
in `git log`.

## 1. Phases and success criteria

### Phase A — Dogfood the cycle-7 Claude Code build

Install the existing cycle-7 Claude Code plugin into
`~/.claude/plugins/metplot/`, run real plotting sessions on real
NetCDF files, capture friction tagged with the six refiner categories
(`alias`, `region`, `pitfall`, `user_pref`, `default`, `failure_mode`)
into `docs/research/2026-05-08-cycle-6-dogfood-findings.md`.

**Stop trigger:** user-driven. Phase A ends when the user says
"enough." No fixed session count, time budget, or coverage threshold.

**Success-criteria evaluation** happens after the user signals
"enough." The findings doc is checked against two questions:

1. **Which applier operations does cycle 6 need to ship?** Each finding
   that maps to `add_alias`, `add_region`, `set_config_default`, or
   `replace_section` justifies that op for cycle 6. Ops with zero
   findings stay TODO with a comment naming cycle 7+ as the deadline.

2. **Are the six refiner categories sufficient?** If findings keep
   wanting to record something that doesn't fit any category, the
   refiner SKILL.md gets a new category before Phase B starts.

If "enough" arrives before either question can be answered (e.g. user
runs zero sessions, or sessions surface zero findings), Phase B
proceeds with the degraded outcome described in §5: allowlist flip +
Claude Code wiring + synthetic-fixture applier tests. Phase A is
*best-effort* evidence gathering, not a gate.

### Phase B — Build the MVP closed loop

Ship every change Phase A justified, on Claude Code only. Other hosts
get the smaller "skill is now available, invoke manually" treatment.

**Phase B is successful when** all of the following hold:

- `python -m tools.build claude-code` produces a payload at
  `build/claude-code/metplot/` that contains:
  - `skills/skill-refiner/SKILL.md` (no longer filtered out).
  - `commands/refine.md` whose body invokes the skill — no "placeholder"
    or "cycle 6" tokens remain.
  - `hooks/refine.json` registering a `Stop` event that runs
    `/metplot:refine` in a fresh subagent, exit-0 always.
- `python -m tools.build {cursor,copilot,gemini-cli,antigravity}`
  payloads each contain `skills/skill-refiner/`.
- `python -m tools.build` payloads for those four hosts have their
  `/refine` (or `.toml` / `.agent/workflows/refine.md`) bodies updated
  to point at the now-shipping skill rather than "cycle 6 will fix this."
- `metplot-refine` correctly applies every fixture under
  `tests/tools/fixtures/refinements/` and never leaves a target file
  in a parse-broken state.
- `pytest -ra`, `ruff check`, and `mypy` are green on the merge commit.

### Out of scope this cycle

- **Codex `/refine`** — Codex's user-defined slash command authoring
  format is still undocumented as of May 2026 (cycle 7 §8.2). Codex
  README updates to "skill-refiner is shipping; invoke manually" but
  the slash command stays absent.
- **Stop hooks on hosts other than Claude Code** — Cursor, Copilot,
  Gemini CLI, Antigravity, and Claude Desktop expose no equivalent
  hook surface (cycle 7 §8.3). Manual `/refine` only on those hosts.
- **MCP-side `log_observation` tool** — `docs/self-improvement.md`
  notes both "agent's filesystem write" and "MCP tool" as task-log
  paths. Cycle 6 takes the filesystem path. MCP tool stays a cycle 7+
  candidate if filesystem writes turn out brittle.
- **Conflicting-refinement automatic merge** — applier flags conflict,
  requires manual merge. Same as today.
- **Refiner self-modification enforcement** — procedural rule in
  SKILL.md, not enforced in code.
- **Real Stop hook firing in CI** — out of scope for an automated test
  harness; manual verification during the post-build dogfood follow-up.

## 2. Phase A artifacts

### 2.1 Findings doc — `docs/research/2026-05-08-cycle-6-dogfood-findings.md`

Created at start of Phase A. Six top-level sections matching the
refiner categories (`alias`, `region`, `pitfall`, `user_pref`,
`default`, `failure_mode`). User fills entries during sessions.

Each entry includes: timestamp, plot request, what the plugin did, the
correction or surprise, the user-stated preference if any, and a
free-text "what should the loop have remembered" line. Format defined
in the tester's guide (`docs/dogfood-tester-guide.md`).

### 2.2 Tester's guide — `docs/dogfood-tester-guide.md`

Evergreen guide (not cycle-scoped). Covers installation, test data
guidance, the six categories with concrete example scenarios per
category, the findings template, an example filled report, and stop
conditions. Reusable for any future dogfood pass.

## 3. Phase B affected surface

### 3.1 Source-of-truth code

| File | Change |
|---|---|
| `targets/_common/skills.py` | Add `"skill-refiner"` to `INCLUDED_SKILLS`; remove "(cycle 6)" comment from docstring. |
| `tools/apply_refinements.py` | Implement the operations Phase A justified (subset of `replace_section`, `add_alias`, `add_region`, `set_config_default`). Operations with zero Phase-A evidence keep their `ClickException("not implemented yet")` body, with the message updated to name the cycle that should complete them. |
| `src/skills/skill-refiner/SKILL.md` | Polish only — drop "cycle 6 will…" framing. May add new category if Phase A revealed one. |

### 3.2 Per-target build wiring

| File | Change |
|---|---|
| `targets/claude-code/build.py` | Real `/refine` body (5–10 lines pointing at the skill). Emit `hooks/refine.json` with `Stop` matcher → fresh-subagent invocation of `/metplot:refine`. |
| `targets/cursor/build.py` | Replace `_refine_md()` placeholder text with "skill is bundled; invoke `skill-refiner` manually." |
| `targets/copilot/build.py` | Same. |
| `targets/gemini-cli/build.py` | Same, for `commands/metplot/refine.toml`. |
| `targets/antigravity/build.py` | Same, for `.agent/workflows/refine.md`. |
| `targets/codex/build.py` | README "Known limitations" updated: skill ships, slash command still deferred. |
| `targets/claude-desktop/README.md` | Manual-invocation guidance (host has no slash-command system). |

### 3.3 Test surface

| File | Status |
|---|---|
| `tests/tools/test_apply_refinements.py` | NEW. One `TestClass` per implemented op. Fixtures: real refinement drafts derived from Phase A findings, stashed under `tests/tools/fixtures/refinements/`. If Phase A produced no findings for a given op, that op's fixtures are synthetic. |
| `tests/tools/fixtures/refinements/` | NEW directory. |
| `tests/targets/_common/test_skills_helper.py` | Flip `test_skill_refiner_not_included` → `test_skill_refiner_included`. Assert `"skill-refiner"` in `INCLUDED_SKILLS`. |
| `tests/targets/claude_code/test_manifest_schema.py` | Flip `test_skill_refiner_excluded` → `test_skill_refiner_included`. |
| `tests/targets/claude_code/test_refine_real.py` | NEW. Asserts `commands/refine.md` does not contain `"placeholder"` or `"cycle 6"`. |
| `tests/targets/claude_code/test_stop_hook.py` | NEW. `hooks/refine.json` exists; has `Stop` matcher; command line invokes the refine slash command. |
| `tests/targets/{cursor,copilot,gemini_cli,antigravity}/test_skills_copied.py` | Flip negative assertions. |
| `tests/targets/{cursor,copilot,gemini_cli,antigravity}/test_commands.py` (or equivalent build-time test) | Assert "placeholder" / "cycle 6" tokens gone from `/refine` body. |
| `tests/targets/test_skill_refiner_cross_host.py` | NEW. Smoke check: every host build contains `skills/skill-refiner/SKILL.md`. |

### 3.4 Documentation

| File | Change |
|---|---|
| `README.md` | Status: skill-refiner is shipping. |
| `docs/architecture.md` | Refiner section drops "future work" framing. |
| `docs/self-improvement.md` | Drop "open question" language for items cycle 6 closed. |
| `targets/<host>/README.md` (each) | Drop "cycle 6 placeholder" mentions; describe current loop state with the partial-host-coverage caveat where applicable. |

## 4. Cross-cutting principles

1. **TDD per cycle 5 / 7 cadence.** One task = one commit + tests. Red → green → commit.

2. **Allowlist flip first.** The `INCLUDED_SKILLS` change has the smallest blast radius and the most negative tests to flip. Doing it first means every later commit operates against the "skill-refiner is real" baseline.

3. **Splice markers, not regex on free text.** `add_alias` and `add_region` target the existing `<!-- REFINER_INSERT_BELOW -->` / `<!-- REFINER_INSERT_ABOVE -->` markers in `aliases.md` and `regions.md`. Never edit by line number.

4. **`regions.json` and `regions.md` stay in sync.** `add_region` updates both. Implementation: text-based splice on `regions.json` to preserve column alignment, validated by re-parsing as JSON before write commits. Re-parse failure rolls back the write.

5. **YAML frontmatter is parsed, not regex'd.** `set_config_default` round-trips via `yaml.safe_load` / `yaml.safe_dump`. Body content preserved verbatim.

6. **Stop hook = fresh subagent, exit-0 always.** The refiner's contract: produce drafts when there's signal, produce nothing otherwise, never break the host's session-end flow.

7. **Applier never silently desyncs.** Every failure mode raises `ClickException` with actionable repro information. A half-applied splice or markdown/JSON divergence is the worst outcome and is explicitly defended against.

8. **Slash-command bodies stay short and procedural.** Each per-host `/refine` body is 5–10 lines: which skill to load, which input to read, which output dir to write, the human-review boundary. No host-specific magic.

## 5. Open risks

- **`regions.json` text-splice fragility.** The file is hand-formatted. If a future commit reformats it, the splice heuristic may misfire. Mitigation: re-parse-validates-or-rolls-back on every splice.

- **Phase A produces no signal.** If the user dogfoods and finds nothing worth recording, the cycle reduces to "ship the allowlist flip + Claude Code wiring + synthetic-fixture applier tests." Acceptable degraded outcome; the loop still closes on Claude Code.

- **Phase A surfaces a missing category.** Adding a category to `skill-refiner/SKILL.md` is a small SKILL.md edit, but it expands the applier's switch on `operation`. If a new category needs a new applier op, Phase B scope grows.

- **Stop hook semantics drift.** Claude Code's hook ergonomics are still evolving as of May 2026. The exit-0-always contract is conservative; if Claude Code adds first-class hook-error UI later, we revisit.

- **Skill bundle size growth.** Each target now copies one extra skill directory. Negligible (~5–10 KB).

## 6. Out-of-scope follow-ons (cycle 7+ candidates)

- Per-host `/refine` slash commands on Cursor, Copilot, Gemini CLI, Antigravity (manual invocation works today; native slash command is polish).
- Codex `/refine` once Codex's slash-command authoring format is documented.
- Dedicated MCP `log_observation` tool if filesystem-write task-log proves brittle.
- Three-way merge for conflicting refinements.
- Web/TUI `metplot-refine` review UI.
- Telemetry on accepted-vs-rejected refinement rates.
