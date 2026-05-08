# Cycle 6 Self-Improvement Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the MVP closed-loop learning layer on Claude Code, with skill-refiner bundled in every host build, applier CLI completed for the operations dogfood evidence justifies, and other-host placeholder text rewritten to point at the now-shipping skill.

**Architecture:** Two phases. Phase A is human evidence-gathering against the cycle-7 Claude Code build (no code change beyond a findings doc template). Phase B is the TDD-driven build that follows. Phase B's applier-op subset is dogfood-justified; Tasks 10–13 are conditional, executed only if Phase A produced ≥1 finding tagged for that op.

**Tech Stack:** Python 3.10+, pytest, click, PyYAML, TOML, the existing build pipeline at `tools/build.py` and per-target builders under `targets/<host>/build.py`.

---

## Plan revision between phases

**This plan is the start-of-cycle-6 version.** After Phase A finishes (user says "enough" per the cycle-6 spec), re-read `docs/research/2026-05-08-cycle-6-dogfood-findings.md` and:

1. Decide which of Tasks 10–13 to execute. Each applier op needs ≥1 dogfood finding tagged for it; ops with zero findings stay TODO with a cycle-7+ deadline (Task 14 covers their error message update).
2. If findings revealed a new refiner category, update `src/skills/skill-refiner/SKILL.md` Categories table (incorporate into Task 8).
3. If findings invalidate a Phase B task as written, edit this plan file as a normal commit before resuming.

The plan revision is itself a no-cost checkpoint — the diff is visible in `git log`.

---

## File Structure

### Created files

| File | Owner task | Responsibility |
|---|---|---|
| `docs/research/2026-05-08-cycle-6-dogfood-findings.md` | Task 1 | Phase A findings template; six sections matching refiner categories. |
| `tests/targets/test_skill_refiner_cross_host.py` | Task 3 | Cross-host smoke test that every build payload contains `skills/skill-refiner/SKILL.md`. |
| `tests/targets/claude_code/test_refine_real.py` | Task 4 | Asserts Claude Code's `commands/refine.md` no longer announces placeholder status. |
| `tests/targets/claude_code/test_stop_hook.py` | Task 5 | Asserts `hooks/refine.json` exists with a `Stop` matcher invoking the refine slash command. |
| `tests/tools/test_apply_refinements.py` | Tasks 10–13 (any executed) | One TestClass per implemented operation. |
| `tests/tools/fixtures/refinements/*.md` | Tasks 10–13 | Refinement drafts derived from Phase A findings (or synthetic if findings empty). |
| `tests/tools/fixtures/skills_tree/` | Tasks 10–13 | Tmp-path-copyable mini source tree used by applier integration tests. |

### Modified files

| File | Owner task | Change |
|---|---|---|
| `targets/_common/skills.py` | Task 2 | Add `"skill-refiner"` to `INCLUDED_SKILLS`; update docstring. |
| `tests/targets/_common/test_skills_helper.py` | Task 2 | Flip `test_skill_refiner_not_included` → asserts inclusion; update `test_included_skills_set`. |
| `tests/targets/claude_code/test_skills_copied.py` | Task 2 | Update `_EXPECTED_SKILLS`; flip `test_skill_refiner_excluded`. |
| `tests/targets/claude_code/test_manifest_schema.py` | Task 2 | Update `test_ships_skills_matches_allowlist`; flip `test_skill_refiner_excluded`. |
| `tests/targets/{cursor,copilot,gemini_cli,codex,antigravity}/test_skills_copied.py` | Task 2 | Update `_EXPECTED`; flip `test_skill_refiner_excluded`. |
| `targets/claude-code/build.py` | Tasks 4 + 5 | Real `/refine` body; emit `hooks/refine.json` registering Stop hook. |
| `tests/targets/claude_code/test_commands_dir.py` | Task 4 | Flip `test_refine_announces_placeholder_status`. |
| `targets/cursor/build.py` | Task 6 | Replace `_refine_md()` placeholder body with manual-invocation guidance. |
| `targets/copilot/build.py` | Task 6 | Replace `commands/refine.md` placeholder body. |
| `targets/gemini-cli/build.py` | Task 6 | Replace `_refine_toml()` placeholder body. |
| `targets/antigravity/build.py` | Task 6 | Replace `_refine_workflow()` placeholder body. |
| `tests/targets/cursor/test_commands.py` | Task 6 | Update `test_refine_announces_placeholder` → asserts manual-invocation guidance. |
| `tests/targets/copilot/test_commands.py` | Task 6 | Same. |
| `tests/targets/gemini_cli/test_commands.py` | Task 6 | Same. |
| `tests/targets/antigravity/test_workflow.py` | Task 6 | Same. |
| `targets/codex/build.py` | Task 7 | README "Known limitations": skill ships, `/refine` slash command still deferred. |
| `targets/claude-desktop/build.py` (or its README emitter) | Task 7 | Manual-invocation guidance section. |
| `src/skills/skill-refiner/SKILL.md` | Task 8 | Drop "cycle 6 will…" framing; optionally add new category if Phase A revealed one. |
| `tools/apply_refinements.py` | Tasks 10–13 + 14 | Implement the operations Phase A justified; update unimplemented-op error messages with cycle 7+ deadline. |
| `README.md` | Task 9 | Status: skill-refiner is shipping. |
| `docs/architecture.md` | Task 9 | Refiner section drops "future work" framing. |
| `docs/self-improvement.md` | Task 9 | Drop "open question" language for items cycle 6 closed. |
| `targets/<host>/README.md` (each) | Task 9 | Drop "cycle 6 placeholder" mentions; describe loop state with partial-host-coverage caveat. |

---

## Task 1: Phase A — findings doc template + install verification

**Phase:** A. No code changes beyond creating one markdown file. The user runs the install + dogfood manually following `docs/dogfood-tester-guide.md`; this task gives them the doc to fill in.

**Files:**
- Create: `docs/research/2026-05-08-cycle-6-dogfood-findings.md`

- [ ] **Step 1: Create the findings doc with template structure**

Write this file:

```markdown
# Cycle 6 dogfood findings

> Phase A of cycle 6 (see `docs/specs/2026-05-08-cycle-6-self-improvement-loop.md`).
> Format and category definitions: `docs/dogfood-tester-guide.md`.

Sessions: 0   Time invested: 0 min
Files exercised: (none yet)

## alias

(no findings yet)

## region

(no findings yet)

## pitfall

(no findings yet)

## user_pref

(no findings yet)

## default

(no findings yet)

## failure_mode

(no findings yet)

## Uncategorized

(no findings yet)

---

## Sign-off

When dogfooding is complete, fill in below and notify whoever's coordinating cycle 6.

- **Sessions completed:** _
- **Findings count by category:** alias=_, region=_, pitfall=_, user_pref=_, default=_, failure_mode=_, uncategorized=_
- **New category proposed:** none / _
- **Stop reason:** (e.g. "categories repeating", "covered all file flavors", "out of test data")
- **Phase B applier ops justified:** (subset of: replace_section, add_alias, add_region, set_config_default)
```

- [ ] **Step 2: Verify the file was created**

Run: `ls docs/research/2026-05-08-cycle-6-dogfood-findings.md`

Expected: file exists.

- [ ] **Step 3: Commit**

```bash
git add docs/research/2026-05-08-cycle-6-dogfood-findings.md
git commit -m "$(cat <<'EOF'
cycle-6 task 1: phase A findings doc template

Empty template with the six refiner categories. The user fills it
during dogfood sessions per docs/dogfood-tester-guide.md. Sign-off
section at the bottom drives the Phase B scope decision (which
applier ops to ship).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 4: Hand off to user for Phase A**

Send a message:

> "Phase A is ready. Install via `docs/dogfood-tester-guide.md`, run sessions, fill the findings doc. Tell me 'enough' when done. I'll then re-evaluate which of Tasks 10–13 are in scope before resuming."

**Stop here. Wait for user to signal "enough."**

---

## Plan-revision checkpoint (between Phase A and Phase B)

After the user signals "enough":

- [ ] **Step 1: Read the findings doc**

Run: `cat docs/research/2026-05-08-cycle-6-dogfood-findings.md`

- [ ] **Step 2: Tabulate which applier ops are justified**

For each finding, identify its mapping:
- `alias` findings → `add_alias` op needed
- `region` findings → `add_region` op needed
- `user_pref` or `default` findings with explicit "always" → `set_config_default` op needed
- `pitfall` or `failure_mode` findings → `append` to a SKILL.md section (already shipping; no new code)
- A finding that proposes a *whole-section rewrite* → `replace_section` op needed

- [ ] **Step 3: Decide Task 10–13 scope**

For each op, decide IN or OUT for cycle 6:
- IN if ≥1 finding maps to it
- OUT if zero findings map; the op stays raising `ClickException` with cycle 7+ deadline (Task 14 covers this)

- [ ] **Step 4: If a new refiner category was proposed in Phase A, fold it into Task 8.**

- [ ] **Step 5: If findings invalidate any Phase B task as written, edit this plan file as a normal commit before resuming.**

- [ ] **Step 6: Announce the revised scope**

Send a message:

> "Phase A complete. N findings across categories: ..., Phase B will execute Tasks 2–9, 14, 15 unconditionally; conditional tasks: ... New category: ..."

Then proceed to Task 2.

---

## Task 2: Allowlist flip — `skill-refiner` shipped in every build

**Phase:** B (always ships).

**Files:**
- Modify: `targets/_common/skills.py:9-15`
- Modify: `tests/targets/_common/test_skills_helper.py:13-21`
- Modify: `tests/targets/claude_code/test_skills_copied.py:10-26`
- Modify: `tests/targets/claude_code/test_manifest_schema.py:34-52`
- Modify: `tests/targets/cursor/test_skills_copied.py:7-19`
- Modify: `tests/targets/copilot/test_skills_copied.py:7-19` (verify line range; same shape as cursor)
- Modify: `tests/targets/gemini_cli/test_skills_copied.py:7-19`
- Modify: `tests/targets/codex/test_skills_copied.py:7-19`
- Modify: `tests/targets/antigravity/test_skills_copied.py:7-19`

**Why this commit is atomic:** the source change (allowlist) and every negative test that asserts exclusion must move together. If split, the suite breaks between commits.

- [ ] **Step 1: Update the allowlist source**

Edit `targets/_common/skills.py`. Find:

```python
INCLUDED_SKILLS = frozenset({
    "netcdf-inspect",
    "netcdf-plot-router",
    "netcdf-plot-map",
    "netcdf-plot-timeseries",
    "netcdf-plot-profile",
})
```

Replace with:

```python
INCLUDED_SKILLS = frozenset({
    "netcdf-inspect",
    "netcdf-plot-router",
    "netcdf-plot-map",
    "netcdf-plot-timeseries",
    "netcdf-plot-profile",
    "skill-refiner",
})
```

Also update the docstring of `copy_skills` (lines 18–26). Find:

```python
    """Copy each cycle-3 skill from `src_root/skills/<name>/` into
    `dst_skills_dir/<name>/`. Excludes `skill-refiner` (cycle 6).
```

Replace with:

```python
    """Copy each shipping skill from `src_root/skills/<name>/` into
    `dst_skills_dir/<name>/`. Includes `skill-refiner` (cycle 6+).
```

- [ ] **Step 2: Update `tests/targets/_common/test_skills_helper.py`**

Edit lines 13–31. Replace:

```python
def test_included_skills_set():
    assert INCLUDED_SKILLS == frozenset({
        "netcdf-inspect", "netcdf-plot-router",
        "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
    })


def test_skill_refiner_not_included():
    assert "skill-refiner" not in INCLUDED_SKILLS


def test_copy_skills_creates_dir_and_returns_names(tmp_path):
    out = tmp_path / "skills"
    names = copy_skills(SRC_ROOT, out)
    assert sorted(names) == sorted(INCLUDED_SKILLS)
    for name in names:
        assert (out / name / "SKILL.md").is_file()
    # Refiner explicitly absent
    assert not (out / "skill-refiner").exists()
```

With:

```python
def test_included_skills_set():
    assert INCLUDED_SKILLS == frozenset({
        "netcdf-inspect", "netcdf-plot-router",
        "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
        "skill-refiner",
    })


def test_skill_refiner_included():
    assert "skill-refiner" in INCLUDED_SKILLS


def test_copy_skills_creates_dir_and_returns_names(tmp_path):
    out = tmp_path / "skills"
    names = copy_skills(SRC_ROOT, out)
    assert sorted(names) == sorted(INCLUDED_SKILLS)
    for name in names:
        assert (out / name / "SKILL.md").is_file()
    # Refiner now shipping
    assert (out / "skill-refiner" / "SKILL.md").is_file()
```

- [ ] **Step 3: Update `tests/targets/claude_code/test_skills_copied.py`**

Edit lines 10–26. Replace `_EXPECTED_SKILLS` to include `"skill-refiner"`:

```python
_EXPECTED_SKILLS = {
    "netcdf-inspect", "netcdf-plot-router",
    "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
    "skill-refiner",
}
```

Replace `test_skill_refiner_excluded`:

```python
def test_skill_refiner_included(built_plugin: Path) -> None:
    """skill-refiner ships from cycle 6 onward."""
    assert (built_plugin / "skills" / "skill-refiner" / "SKILL.md").is_file()
```

- [ ] **Step 4: Update `tests/targets/claude_code/test_manifest_schema.py`**

Edit lines 34–52. Replace `test_ships_skills_matches_allowlist`:

```python
def test_ships_skills_matches_allowlist(built_plugin: Path) -> None:
    m = json.loads((built_plugin / ".claude-plugin" / "plugin.json").read_text())
    expected = {
        "netcdf-inspect", "netcdf-plot-router",
        "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
        "skill-refiner",
    }
    assert set(m["metplot"]["ships_skills"]) == expected
```

Replace `test_skill_refiner_excluded`:

```python
def test_skill_refiner_advertised(built_plugin: Path) -> None:
    """skill-refiner ships in the metplot manifest block from cycle 6."""
    m = json.loads((built_plugin / ".claude-plugin" / "plugin.json").read_text())
    assert "skill-refiner" in m["metplot"]["ships_skills"]
```

- [ ] **Step 5: Update each per-host `test_skills_copied.py`**

For each of `cursor`, `copilot`, `gemini_cli`, `codex`, `antigravity`:

Edit `tests/targets/<host>/test_skills_copied.py`. The file currently has:

```python
_EXPECTED = {
    "netcdf-inspect", "netcdf-plot-router",
    "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
}
```

Add `"skill-refiner"` to the set. Then replace:

```python
def test_skill_refiner_excluded(built_plugin: Path):
    assert not (built_plugin / "skills" / "skill-refiner").exists()
```

With:

```python
def test_skill_refiner_included(built_plugin: Path):
    assert (built_plugin / "skills" / "skill-refiner" / "SKILL.md").is_file()
```

- [ ] **Step 6: Run the suite to verify it fails on tests that haven't been updated**

Run: `pytest tests/targets -x -q`

Expected: only the tests you updated should pass; if there's another reference to "skill-refiner" exclusion that you missed, this run surfaces it. Iterate until all tests pass.

- [ ] **Step 7: Run the full suite**

Run: `pytest -q`

Expected: PASS (all tests).

- [ ] **Step 8: Run lint**

Run: `ruff check`

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add targets/_common/skills.py tests/targets
git commit -m "$(cat <<'EOF'
cycle-6 task 2: ship skill-refiner in every host build

Add "skill-refiner" to INCLUDED_SKILLS. All seven host builds now
copy the refiner skill into their skills/ directory; the manifest's
ships_skills block advertises it.

Negative-assertion tests across every host (test_skill_refiner_excluded
and friends) flipped to test_skill_refiner_included in the same commit
so the suite stays green.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Cross-host smoke test

**Phase:** B (always ships).

**Files:**
- Create: `tests/targets/test_skill_refiner_cross_host.py`

- [ ] **Step 1: Write the cross-host test**

Create `tests/targets/test_skill_refiner_cross_host.py`:

```python
"""Smoke check: every host build payload contains the skill-refiner skill.

Catches future regressions where a target build accidentally re-filters
skill-refiner out (e.g. via a path filter or a mistaken second allowlist).
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"

_TARGETS = [
    "claude_code", "claude_desktop", "codex", "cursor",
    "copilot", "gemini_cli", "antigravity", "hermes",
]


def _build_module_name(host: str) -> str:
    # gemini_cli (snake) → gemini-cli (kebab) for the directory name
    return host.replace("_", "-")


@pytest.mark.parametrize("host", _TARGETS)
def test_skill_refiner_in_build(host: str, tmp_path: Path) -> None:
    """Every target build emits a skills/skill-refiner/SKILL.md file."""
    dir_name = _build_module_name(host)
    mod = importlib.import_module(f"targets.{host}.build")
    out_root = tmp_path / host
    mod.build(SRC_ROOT, out_root)

    # Find the plugin payload: targets emit at out_root/metplot/ (claude-code,
    # codex, cursor, copilot, gemini-cli, antigravity, claude-desktop) or
    # out_root/<bundle>/ for hermes.
    plugin_dir = out_root / "metplot"
    if not plugin_dir.exists():
        # Hermes uses a different layout: skills/ at out_root.
        plugin_dir = out_root

    skill_md = plugin_dir / "skills" / "skill-refiner" / "SKILL.md"
    if not skill_md.exists():
        # Antigravity puts skills under .agent/skills/
        skill_md = plugin_dir / ".agent" / "skills" / "skill-refiner" / "SKILL.md"

    assert skill_md.is_file(), (
        f"{host}: skill-refiner SKILL.md not found at any expected path "
        f"(checked plugin_dir/skills and plugin_dir/.agent/skills)")
```

- [ ] **Step 2: Run the test**

Run: `pytest tests/targets/test_skill_refiner_cross_host.py -v`

Expected: PASS for every target.

- [ ] **Step 3: Commit**

```bash
git add tests/targets/test_skill_refiner_cross_host.py
git commit -m "$(cat <<'EOF'
cycle-6 task 3: cross-host smoke test for skill-refiner

Parametrized check that every target build emits skill-refiner under
its canonical skills/ path (or .agent/skills/ for Antigravity). Catches
future regressions where a build path filter or accidental second
allowlist re-excludes the refiner.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Claude Code real `/refine` command body

**Phase:** B (always ships).

**Files:**
- Modify: `targets/claude-code/build.py:112-134` (the `_refine_command_md` helper)
- Modify: `tests/targets/claude_code/test_commands_dir.py:23-27`
- Create: `tests/targets/claude_code/test_refine_real.py`

- [ ] **Step 1: Write the failing real-/refine test**

Create `tests/targets/claude_code/test_refine_real.py`:

```python
"""Cycle-6: /refine is no longer a placeholder."""
from __future__ import annotations

from pathlib import Path


def test_refine_does_not_announce_placeholder(built_plugin: Path) -> None:
    text = (built_plugin / "commands" / "refine.md").read_text().lower()
    assert "placeholder" not in text, (
        "refine.md still announces placeholder status — should invoke "
        "skill-refiner directly per cycle 6")
    assert "cycle 6 will" not in text


def test_refine_invokes_skill_refiner(built_plugin: Path) -> None:
    text = (built_plugin / "commands" / "refine.md").read_text()
    assert "skill-refiner" in text, (
        "refine.md should name the skill-refiner skill so the agent "
        "knows what to load")


def test_refine_mentions_task_log(built_plugin: Path) -> None:
    text = (built_plugin / "commands" / "refine.md").read_text()
    assert ".metplot/task-log.jsonl" in text or "task-log" in text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/targets/claude_code/test_refine_real.py -v`

Expected: FAIL (current `_refine_command_md` says "placeholder" and "cycle 6").

- [ ] **Step 3: Update the existing placeholder-status test (it will start failing as soon as we fix the body)**

Edit `tests/targets/claude_code/test_commands_dir.py` lines 23–27. Replace:

```python
def test_refine_announces_placeholder_status(built_plugin: Path) -> None:
    """User-facing text should make clear this is a placeholder."""
    text = (built_plugin / "commands" / "refine.md").read_text()
    assert "placeholder" in text.lower()
    assert "cycle 6" in text.lower()
```

With:

```python
def test_refine_announces_real_invocation(built_plugin: Path) -> None:
    """Cycle-6: /refine invokes skill-refiner; no placeholder framing."""
    text = (built_plugin / "commands" / "refine.md").read_text().lower()
    assert "skill-refiner" in text
    assert "placeholder" not in text
```

- [ ] **Step 4: Replace `_refine_command_md` in `targets/claude-code/build.py`**

Edit lines 112–134. Replace the entire `_refine_command_md` function with:

```python
def _refine_command_md() -> str:
    return (
        "---\n"
        "description: Review the current session and propose refinement "
        "drafts to the canonical metplot skills based on what was learned. "
        "Reads .metplot/task-log.jsonl; writes drafts to "
        ".metplot/refinements/ for human review via metplot-refine.\n"
        "---\n"
        "\n"
        "Load `skills/skill-refiner/SKILL.md` and follow its procedure "
        "against `.metplot/task-log.jsonl`. Produce draft refinements "
        "under `.metplot/refinements/<timestamp>-<skill>-<tag>.md`.\n"
        "\n"
        "Do not modify any file under `src/skills/`. Drafts are reviewed "
        "out of band by the user via `metplot-refine`.\n"
        "\n"
        "If `.metplot/task-log.jsonl` is missing or empty, exit cleanly "
        "without writing drafts — that's a no-signal session, not an error.\n"
    )
```

- [ ] **Step 5: Run both tests to verify they pass**

Run: `pytest tests/targets/claude_code/test_refine_real.py tests/targets/claude_code/test_commands_dir.py -v`

Expected: PASS.

- [ ] **Step 6: Run the full suite**

Run: `pytest -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add targets/claude-code/build.py tests/targets/claude_code/test_refine_real.py tests/targets/claude_code/test_commands_dir.py
git commit -m "$(cat <<'EOF'
cycle-6 task 4: real /refine command on Claude Code

commands/refine.md no longer announces placeholder status. Body
instructs the agent to load skill-refiner SKILL.md, run against
.metplot/task-log.jsonl, and write drafts under .metplot/refinements/.

Existing test_refine_announces_placeholder_status flipped to
test_refine_announces_real_invocation. New test_refine_real.py
adds the positive assertions (names skill-refiner, mentions task-log).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Claude Code Stop hook

**Phase:** B (always ships).

**Files:**
- Modify: `targets/claude-code/build.py:67-79` (extend the existing hooks block, or add a sibling JSON file)
- Create: `tests/targets/claude_code/test_stop_hook.py`
- Modify: `tests/targets/claude_code/test_no_hooks.py:10-15` (the manifest-level no-hooks check stays as-is; verify nothing else regresses)

- [ ] **Step 1: Write the failing Stop-hook test**

Create `tests/targets/claude_code/test_stop_hook.py`:

```python
"""Cycle-6: Stop hook fires skill-refiner at session end."""
from __future__ import annotations

import json
from pathlib import Path


def test_refine_hook_file_present(built_plugin: Path) -> None:
    assert (built_plugin / "hooks" / "refine.json").is_file(), (
        "Cycle-6 ships a Stop hook at hooks/refine.json")


def test_refine_hook_has_stop_event(built_plugin: Path) -> None:
    config = json.loads((built_plugin / "hooks" / "refine.json").read_text())
    assert "Stop" in config, (
        f"refine.json must register a Stop event; got keys: {list(config)}")
    entries = config["Stop"]
    assert isinstance(entries, list) and entries, (
        "Stop event should be a non-empty list")


def test_stop_hook_invokes_refine_command(built_plugin: Path) -> None:
    config = json.loads((built_plugin / "hooks" / "refine.json").read_text())
    entry = config["Stop"][0]
    assert "hooks" in entry
    cmd_block = entry["hooks"][0]
    assert cmd_block["type"] == "command"
    cmd = cmd_block["command"]
    # Must invoke /refine slash command (or /metplot:refine namespace form).
    assert "/refine" in cmd or "/metplot:refine" in cmd, (
        f"Stop hook command does not invoke /refine: {cmd!r}")


def test_stop_hook_matcher_is_wildcard(built_plugin: Path) -> None:
    config = json.loads((built_plugin / "hooks" / "refine.json").read_text())
    entry = config["Stop"][0]
    assert entry.get("matcher") == "*", (
        "Stop hook should match all sessions (matcher=*)")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/targets/claude_code/test_stop_hook.py -v`

Expected: FAIL with "hooks/refine.json" missing.

- [ ] **Step 3: Update `targets/claude-code/build.py` to emit the Stop hook**

Edit lines 67–79 (after the existing `setup.json` write). Add a sibling write for `refine.json`. Replace the block:

```python
    # SessionStart hook (auto-fire setup on first run / version bump)
    hooks_dir = plugin_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    (hooks_dir / "setup.json").write_text(json.dumps({
        "SessionStart": [{
            "matcher": "*",
            "hooks": [{
                "type": "command",
                "command": "${CLAUDE_PLUGIN_ROOT}/setup.sh --quiet",
            }],
        }],
    }, indent=2) + "\n")
```

With:

```python
    # SessionStart hook (auto-fire setup on first run / version bump)
    hooks_dir = plugin_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    (hooks_dir / "setup.json").write_text(json.dumps({
        "SessionStart": [{
            "matcher": "*",
            "hooks": [{
                "type": "command",
                "command": "${CLAUDE_PLUGIN_ROOT}/setup.sh --quiet",
            }],
        }],
    }, indent=2) + "\n")

    # Cycle-6 Stop hook: fires skill-refiner in a fresh subagent at
    # session end. Exit 0 always — no-signal sessions are normal.
    (hooks_dir / "refine.json").write_text(json.dumps({
        "Stop": [{
            "matcher": "*",
            "hooks": [{
                "type": "command",
                "command": "claude --print '/metplot:refine' || true",
            }],
        }],
    }, indent=2) + "\n")
```

The `|| true` enforces exit-0-always at the shell level. The `claude --print` form spawns a fresh subagent that loads the slash command body in isolation.

- [ ] **Step 4: Run the Stop-hook test**

Run: `pytest tests/targets/claude_code/test_stop_hook.py -v`

Expected: PASS.

- [ ] **Step 5: Run the existing no-hooks-in-manifest test to ensure nothing regressed**

Run: `pytest tests/targets/claude_code/test_no_hooks.py -v`

Expected: PASS (the manifest-level check is unrelated to `hooks/` directory contents).

- [ ] **Step 6: Run the full suite**

Run: `pytest -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add targets/claude-code/build.py tests/targets/claude_code/test_stop_hook.py
git commit -m "$(cat <<'EOF'
cycle-6 task 5: Claude Code Stop hook for skill-refiner

hooks/refine.json registers a Stop event matching all sessions. The
hook command invokes /metplot:refine via 'claude --print' which spawns
a fresh subagent (isolated from the user's primary context). The
trailing '|| true' enforces exit-0-always at the shell level so a
missing task-log or refiner error doesn't break the user's session-end.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Other-host placeholder text → manual-invocation guidance

**Phase:** B (always ships). One commit per host, four total commits.

**Files** (per host):
- Modify: `targets/<host>/build.py` (the per-host `_refine_*` helper)
- Modify: `tests/targets/<host>/test_commands.py` or `test_workflow.py`

The shape is identical across `cursor`, `copilot`, `gemini-cli`, and `antigravity`. Below is the cursor variant in full; the other three follow the same red→green→commit pattern with the file paths and slash-command syntax substituted.

### Task 6a: Cursor

- [ ] **Step 1: Update the test to assert real invocation**

Edit `tests/targets/cursor/test_commands.py`. Find any test asserting "placeholder" or "cycle 6"; replace with the assertion below. (If `tests/targets/cursor/test_commands.py` doesn't have a placeholder test, check `test_build_runs.py` and update there.)

```python
def test_refine_invokes_skill_refiner(built_plugin: Path):
    text = (built_plugin / "commands" / "refine.md").read_text().lower()
    assert "skill-refiner" in text
    assert "placeholder" not in text
    assert "cycle 6" not in text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/targets/cursor/test_commands.py::test_refine_invokes_skill_refiner -v`

Expected: FAIL.

- [ ] **Step 3: Update `_refine_md` in `targets/cursor/build.py`**

Edit lines 77–end of `_refine_md`. Replace the function body with:

```python
def _refine_md() -> str:
    return (
        "---\n"
        "description: Review the current session and propose refinement "
        "drafts to the canonical metplot skills. Manually-invoked on Cursor "
        "(no Stop hook on this host).\n"
        "---\n\n"
        "Load `skills/skill-refiner/SKILL.md` and follow its procedure "
        "against `.metplot/task-log.jsonl`. Produce draft refinements "
        "under `.metplot/refinements/<timestamp>-<skill>-<tag>.md`.\n\n"
        "Do not modify any file under `src/skills/`. Drafts are reviewed "
        "out of band by the user via `metplot-refine`.\n\n"
        "If `.metplot/task-log.jsonl` is missing or empty, exit cleanly "
        "without writing drafts — that's a no-signal session, not an error.\n"
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/targets/cursor -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add targets/cursor/build.py tests/targets/cursor
git commit -m "$(cat <<'EOF'
cycle-6 task 6a: Cursor /refine invokes skill-refiner

Body rewritten from "placeholder, cycle 6 will fix this" to the
real invocation: load skill-refiner SKILL.md, follow its procedure,
write drafts to .metplot/refinements/. Cursor has no Stop hook
equivalent so this is manual-only.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 6b: Copilot

Same pattern as 6a. Files: `targets/copilot/build.py` (the inline `commands/refine.md` write at lines 66–73 of the build) and `tests/targets/copilot/test_commands.py:13-15`.

- [ ] **Step 1: Update `tests/targets/copilot/test_commands.py` lines 13–15.** Replace `test_refine_announces_placeholder` with `test_refine_invokes_skill_refiner` using the same assertion shape as 6a Step 1.

- [ ] **Step 2: Run the test to verify it fails.**

Run: `pytest tests/targets/copilot/test_commands.py::test_refine_invokes_skill_refiner -v`

Expected: FAIL.

- [ ] **Step 3: Update the `commands/refine.md` write in `targets/copilot/build.py`.** Find the call:

```python
    (commands_dir / "refine.md").write_text(
```

Replace the body argument with the same string content as Task 6a Step 3 (cursor's `_refine_md` body).

- [ ] **Step 4: Run the test to verify it passes.**

Run: `pytest tests/targets/copilot -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add targets/copilot/build.py tests/targets/copilot
git commit -m "cycle-6 task 6b: Copilot /refine invokes skill-refiner

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 6c: Gemini CLI

Files: `targets/gemini-cli/build.py:81-end of _refine_toml` and `tests/targets/gemini_cli/test_commands.py:26-28`.

- [ ] **Step 1: Update `tests/targets/gemini_cli/test_commands.py` lines 26–28.** Replace `test_refine_announces_placeholder`:

```python
def test_refine_invokes_skill_refiner(built_plugin: Path):
    text = (built_plugin / "commands" / "metplot" / "refine.toml").read_text().lower()
    assert "skill-refiner" in text
    assert "placeholder" not in text
    assert "cycle 6" not in text
```

- [ ] **Step 2: Run the test to verify it fails.**

Run: `pytest tests/targets/gemini_cli/test_commands.py::test_refine_invokes_skill_refiner -v`

Expected: FAIL.

- [ ] **Step 3: Update `_refine_toml` in `targets/gemini-cli/build.py`.** Replace its body with:

```python
def _refine_toml() -> str:
    return (
        'description = "Review the current session and propose refinement '
        'drafts to the canonical metplot skills. Manually-invoked on '
        'Gemini CLI (no Stop hook on this host)."\n'
        'prompt = "Load skills/skill-refiner/SKILL.md and follow its '
        'procedure against .metplot/task-log.jsonl. Write drafts under '
        '.metplot/refinements/. Do not modify src/skills/ directly. '
        'If the task-log is missing or empty, exit cleanly."\n'
    )
```

- [ ] **Step 4: Run the test to verify it passes.**

Run: `pytest tests/targets/gemini_cli -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add targets/gemini-cli/build.py tests/targets/gemini_cli
git commit -m "cycle-6 task 6c: Gemini CLI /metplot:refine invokes skill-refiner

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 6d: Antigravity

Files: `targets/antigravity/build.py:78-92 (_refine_workflow)` and `tests/targets/antigravity/test_workflow.py:10-12`.

- [ ] **Step 1: Update `tests/targets/antigravity/test_workflow.py` lines 10–12.** Replace:

```python
def test_refine_invokes_skill_refiner(built_plugin: Path):
    text = (built_plugin / ".agent" / "workflows" / "refine.md").read_text().lower()
    assert "skill-refiner" in text
    assert "placeholder" not in text
    assert "cycle 6" not in text
```

- [ ] **Step 2: Run the test to verify it fails.**

Run: `pytest tests/targets/antigravity/test_workflow.py::test_refine_invokes_skill_refiner -v`

Expected: FAIL.

- [ ] **Step 3: Update `_refine_workflow` in `targets/antigravity/build.py`.** Replace its body with:

```python
def _refine_workflow() -> str:
    return (
        "---\n"
        "description: Review the current session and propose refinement "
        "drafts. Manually-invoked workflow (Antigravity has no Stop hook).\n"
        "---\n\n"
        "# /refine workflow\n\n"
        "Load `.agent/skills/skill-refiner/SKILL.md` and follow its "
        "procedure against `.metplot/task-log.jsonl`. Write drafts under "
        "`.metplot/refinements/<timestamp>-<skill>-<tag>.md`.\n\n"
        "Do not modify any file under `src/skills/`. Drafts are reviewed "
        "out of band by the user via `metplot-refine`.\n\n"
        "If `.metplot/task-log.jsonl` is missing or empty, exit cleanly "
        "without writing drafts.\n"
    )
```

- [ ] **Step 4: Run the test to verify it passes.**

Run: `pytest tests/targets/antigravity -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add targets/antigravity/build.py tests/targets/antigravity
git commit -m "cycle-6 task 6d: Antigravity /refine workflow invokes skill-refiner

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Codex + Claude Desktop README updates

**Phase:** B (always ships).

Codex stays without a `/refine` slash command (authoring format still undocumented). Claude Desktop has no slash-command system. Both READMEs need the cycle-6 status reflected.

**Files:**
- Modify: `targets/codex/build.py:124-133` (the "Known limitations" section)
- Modify: `targets/claude-desktop/build.py` (locate the README emitter; add manual-invocation section)

- [ ] **Step 1: Update Codex README's "Known limitations" section in `targets/codex/build.py`**

Find lines 126–133:

```python
        "## Known limitations (cycle 7)\n\n"
        "- **No custom slash command.** Codex's user-defined `/foo` "
        "authoring format is undocumented as of May 2026; we omit a "
        "`/refine` command. To trigger refinement (cycle 6), use the "
        "skill-refiner skill directly.\n"
        "- **No hooks.** Cycle-6 self-improvement Stop hook will be "
        "added in a follow-up.\n"
    )
```

Replace with:

```python
        "## Known limitations\n\n"
        "- **No custom slash command for /refine.** Codex's user-defined "
        "`/foo` authoring format is undocumented as of May 2026; we omit "
        "a `/refine` command. The skill-refiner skill itself ships in "
        "this build (`skills/skill-refiner/`) — invoke it manually by "
        "asking the agent to \"run skill-refiner against the current "
        "session\" at the end of a plotting session.\n"
        "- **No Stop hook.** Codex has no Stop event analogous to Claude "
        "Code's. Refinement is manual on this host.\n"
    )
```

- [ ] **Step 2: Locate Claude Desktop README emitter**

Run: `grep -n "Manual invoc\|skill-refiner\|refine" targets/claude-desktop/build.py`

Find the README emitter function (likely `_plugin_readme` or similar).

- [ ] **Step 3: Add a "Self-improvement loop" section to the Claude Desktop README**

Insert this section near the end of the README content (before any "## License" or trailing footer):

```python
        "## Self-improvement loop\n\n"
        "Claude Desktop has no slash-command authoring system, so the "
        "skill-refiner skill is invoked manually. At the end of a "
        "plotting session, ask the assistant: \"run skill-refiner "
        "against this session.\" The skill reads "
        "`.metplot/task-log.jsonl` and writes draft refinements to "
        "`.metplot/refinements/<timestamp>-<skill>-<tag>.md`.\n\n"
        "Out of band, run `metplot-refine` (installed by the bundled "
        "setup script) to review and apply drafts to the canonical "
        "skills in `src/skills/`.\n\n"
        "There is no Stop hook on Claude Desktop. Refinement is "
        "always manual on this host.\n\n"
```

- [ ] **Step 4: Build and inspect both targets**

```bash
python -m tools.build codex
python -m tools.build claude-desktop
grep -n "skill-refiner" build/codex/metplot/README.md
grep -n "skill-refiner" build/claude-desktop/metplot/README.md
```

Expected: both READMEs mention skill-refiner with manual-invocation guidance; Codex README no longer says "(cycle 7)" or "Cycle-6 self-improvement Stop hook will be added."

- [ ] **Step 5: Run the suite**

Run: `pytest -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add targets/codex/build.py targets/claude-desktop/build.py
git commit -m "$(cat <<'EOF'
cycle-6 task 7: Codex + Claude Desktop READMEs reflect shipping refiner

Codex 'Known limitations' updated: skill-refiner is bundled in this
build; the /refine slash command stays absent only because Codex's
slash-command authoring format is still undocumented. Manual invocation
is the path on Codex.

Claude Desktop README adds a 'Self-improvement loop' section explaining
manual invocation (the host has no slash-command system at all). Stop
hook unavailable on this host.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Polish `skill-refiner/SKILL.md`

**Phase:** B (always ships). Drop "cycle 6 will…" framing now that the skill is shipping.

**Files:**
- Modify: `src/skills/skill-refiner/SKILL.md`

- [ ] **Step 1: Read the current SKILL.md**

Run: `cat src/skills/skill-refiner/SKILL.md`

- [ ] **Step 2: Remove forward-looking "cycle 6 will" / "future" framing**

Edit `src/skills/skill-refiner/SKILL.md`. Search for the strings: `"cycle 6 will"`, `"will trigger"`, `"once cycle 6"`, `"future"`. Replace each occurrence so the text describes current behavior in present tense rather than future tense.

For example, if the text says:

```
Once cycle 6 ships, the Stop hook will fire this skill at session end.
```

Change to:

```
On Claude Code, the Stop hook fires this skill at session end (cycle 6+).
On hosts without a Stop event, invoke /refine manually.
```

- [ ] **Step 3: If Phase A revealed a new refiner category, add it to the Categories table**

Look at the findings doc's Sign-off section line "New category proposed:". If it names a category, add a row to the Categories table in `SKILL.md` with the format used by existing rows (`tag | meaning | refines`).

If no new category was proposed, skip this step.

- [ ] **Step 4: Run skill lint**

Run: `python -m tools.lint_skills`

Expected: PASS — SKILL.md frontmatter still valid.

- [ ] **Step 5: Run the suite**

Run: `pytest -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/skills/skill-refiner/SKILL.md
git commit -m "$(cat <<'EOF'
cycle-6 task 8: drop "cycle 6 will" framing in skill-refiner SKILL.md

The skill is shipping now; describe behavior in present tense. Stop
hook firing is host-specific (Claude Code only); manual invocation
covers the other hosts.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Documentation updates

**Phase:** B (always ships). One commit covering all doc files.

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/self-improvement.md`
- Modify: `targets/claude-code/README.md`
- Modify: `targets/cursor/README.md` (if exists; create reference if not)
- Modify: `targets/copilot/README.md` (if exists)
- Modify: `targets/gemini-cli/README.md` (if exists)
- Modify: `targets/antigravity/README.md` (if exists)
- Modify: `targets/codex/README.md` (if exists)
- Modify: `targets/claude-desktop/README.md` (if exists)

- [ ] **Step 1: Update root `README.md`**

In the section that describes self-improvement / refiner status (search for "skill-refiner" or "self-improvement"), replace any "TODO" / "stub" / "future cycle" framing with present-tense status. Add a note that Claude Code has full closed-loop coverage (Stop hook + slash command) and other hosts are manual-only.

Suggested addition near the existing "Self-improvement loop" section:

```markdown
**Status:** shipping. The `skill-refiner` skill ships in every host
build. Claude Code triggers the loop automatically via a `Stop` hook
at session end. Other hosts (Cursor, Copilot, Gemini CLI, Antigravity,
Claude Desktop) require manual invocation. Codex is supported via
manual invocation; native slash command pending Codex's
slash-command authoring docs.
```

- [ ] **Step 2: Update `docs/architecture.md`**

Search for any reference to the refiner being "future work" or "cycle 6." Replace with the current state.

- [ ] **Step 3: Update `docs/self-improvement.md`**

The "Open questions" section may still list items closed by cycle 6. Move closed items to a new "Resolved (cycle 6)" subsection so the history is preserved. Keep open items where they are (concept drift, three-way merge, refiner-proposes-new-skills).

- [ ] **Step 4: Update each per-target README.md**

Run: `find targets -name "README.md" | xargs grep -l "cycle 6\|placeholder"`

For each file the command lists, find the placeholder/cycle-6 mention and replace with the current state. Pattern:

- Claude Code README: "Skill-refiner + Stop hook" section now describes shipping behavior, not deferred.
- Other hosts: note that skill-refiner is bundled and `/refine` (or workflow / TOML) invokes it manually; no Stop hook on this host.

- [ ] **Step 5: Run skill lint and the full suite**

```bash
python -m tools.lint_skills
pytest -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add README.md docs/ targets/*/README.md
git commit -m "$(cat <<'EOF'
cycle-6 task 9: docs reflect shipping self-improvement loop

Root README, architecture.md, self-improvement.md, and every
per-target README drop "cycle 6 will" / "placeholder" framing and
describe current state: skill-refiner ships everywhere; Claude Code
has Stop hook + slash command; other hosts are manual-only; Codex
slash command still deferred pending host docs.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Implement `replace_section` op (CONDITIONAL)

**Phase:** B. **Skip if Phase A produced zero findings that map to `replace_section`.** A `replace_section` finding is one where the user proposed rewriting a whole `## Section` of a SKILL.md (rare; needs strong evidence).

**Files:**
- Modify: `tools/apply_refinements.py:93-95` (replace the `ClickException` body with a real implementation)
- Create: `tests/tools/test_apply_refinements.py` (if not yet created by an earlier op task)
- Create: `tests/tools/fixtures/refinements/replace_section_*.md` (one per Phase A finding tagged for this op; synthetic if zero)

- [ ] **Step 1: Create the fixture refinement draft**

For each Phase A finding tagged for this op, write a fixture file under `tests/tools/fixtures/refinements/`. Example fixture for replace_section:

```markdown
---
target: src/skills/netcdf-plot-map/SKILL.md
section: Verification
operation: replace_section
confidence: high
evidence:
  - dogfood session 2026-05-08T19:30Z
  - user said "the existing verification list is wrong order; here's a better one"
---

- Confirm the variable name resolved correctly (compare against `attrs['long_name']`).
- Confirm the slice is non-empty (`data.size > 0`).
- Confirm the time window matches the request (first / last timestamps printed).
- Confirm units are reported on the colorbar.
- Confirm the projection is appropriate for the latitude range.
```

If Phase A had no `replace_section` findings, write **one synthetic fixture** in the same shape using the example above. Document at the top of the file: `<!-- synthetic fixture; no Phase A finding -->`.

- [ ] **Step 2: Write the failing test**

Create or extend `tests/tools/test_apply_refinements.py`:

```python
"""Cycle-6: applier operations end-to-end."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tools.apply_refinements import (
    apply_refinement,
    parse_refinement,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "refinements"
SKILLS_FIXTURE = Path(__file__).parent / "fixtures" / "skills_tree"


@pytest.fixture
def skills_tree(tmp_path, monkeypatch):
    """Tmp-path copy of src/skills/ so applier tests don't touch real files."""
    dst = tmp_path / "skills"
    shutil.copytree(REPO_ROOT / "src" / "skills", dst)
    # Repoint REPO_ROOT in the applier so its `target` resolution lands here
    monkeypatch.setattr("tools.apply_refinements.REPO_ROOT", tmp_path)
    # Move the skill tree under `tmp_path/src/skills/` to mirror real layout
    (tmp_path / "src").mkdir()
    shutil.move(str(dst), str(tmp_path / "src" / "skills"))
    return tmp_path


class TestReplaceSection:
    def test_replaces_named_section_body(self, skills_tree):
        fixture = next(FIXTURES_DIR.glob("replace_section_*.md"))
        ref = parse_refinement(fixture)
        target = skills_tree / ref["meta"]["target"]
        assert target.exists()

        apply_refinement(ref)

        new = target.read_text()
        # Section header preserved
        assert f"## {ref['meta']['section']}\n" in new
        # New body lines are present
        for line in ref["body"].splitlines():
            if line.strip():
                assert line.strip() in new

    def test_missing_section_raises(self, skills_tree, tmp_path):
        # Synthesize a draft pointing at a section that doesn't exist
        bad = tmp_path / "bad.md"
        bad.write_text(
            "---\n"
            "target: src/skills/netcdf-plot-map/SKILL.md\n"
            "section: NonexistentSection\n"
            "operation: replace_section\n"
            "confidence: high\n"
            "evidence: []\n"
            "---\n\n"
            "body that won't apply\n"
        )
        ref = parse_refinement(bad)
        with pytest.raises(Exception, match="section"):
            apply_refinement(ref)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `pytest tests/tools/test_apply_refinements.py::TestReplaceSection -v`

Expected: FAIL — `apply_refinement` raises `replace_section not implemented yet` for the first test; the second test depends on the same code path.

- [ ] **Step 4: Implement `replace_section` in `tools/apply_refinements.py`**

Edit lines 93–95. Replace:

```python
    elif op == "replace_section":
        # TODO
        raise click.ClickException("replace_section not implemented yet")
```

With:

```python
    elif op == "replace_section":
        if not section:
            raise click.ClickException("replace_section operation requires `section`")
        apply_replace_section(target, section, body)
```

Then add a new function above `apply_refinement` (after `apply_append`):

```python
def apply_replace_section(target: Path, section: str, body: str) -> str:
    """Replace the body of a named section in `target`. Return the
    new section text. Raises ValueError if the section header is not
    present in the file."""
    text = target.read_text()
    pattern = re.compile(
        rf"^(##\s+{re.escape(section)}\s*\n)(.*?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        raise ValueError(f"section '{section}' not found in {target}")
    new_section = m.group(1) + "\n" + body.strip() + "\n\n"
    new_text = text[:m.start()] + new_section + text[m.end():]
    target.write_text(new_text)
    return new_section
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/tools/test_apply_refinements.py::TestReplaceSection -v`

Expected: PASS.

- [ ] **Step 6: Run the full suite**

Run: `pytest -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add tools/apply_refinements.py tests/tools/test_apply_refinements.py tests/tools/fixtures/refinements/replace_section_*.md
git commit -m "$(cat <<'EOF'
cycle-6 task 10: apply_refinements.replace_section op

apply_replace_section locates a `## SectionName` header in the target
SKILL.md and replaces the body up to the next `##` heading. Header
text preserved; body text from the draft replaces existing content.

Test fixtures derived from Phase A dogfood findings (or synthetic if
no findings tagged this op).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Implement `add_alias` op (CONDITIONAL)

**Phase:** B. **Skip if Phase A produced zero findings that map to `add_alias`.**

**Files:**
- Modify: `tools/apply_refinements.py:96-98`
- Modify: `tests/tools/test_apply_refinements.py` (add TestAddAlias class)
- Create: `tests/tools/fixtures/refinements/add_alias_*.md` (one per Phase A finding tagged for this op; synthetic if zero)

The splice target is `src/skills/netcdf-inspect/references/aliases.md` between markers `<!-- REFINER_INSERT_BELOW -->` and `<!-- REFINER_INSERT_ABOVE -->`.

- [ ] **Step 1: Create the fixture(s)**

Example fixture from a Phase A alias finding:

```markdown
---
target: src/skills/netcdf-inspect/references/aliases.md
operation: add_alias
confidence: high
evidence:
  - dogfood session 2026-05-08T18:42Z
  - file is CMIP6, user said "it's tos not sst"
---

| SST (CMIP6) | `tos` | NorESM2-LM, MPI-ESM, etc. |
```

The body is exactly one markdown table row. The applier splices it between the markers in `aliases.md`.

If Phase A had no findings, write a synthetic fixture in the same shape with a top-of-file comment marking it synthetic.

- [ ] **Step 2: Write the failing test**

Add to `tests/tools/test_apply_refinements.py`:

```python
class TestAddAlias:
    MARKER_BELOW = "<!-- REFINER_INSERT_BELOW -->"
    MARKER_ABOVE = "<!-- REFINER_INSERT_ABOVE -->"

    def test_inserts_row_between_markers(self, skills_tree):
        fixture = next(FIXTURES_DIR.glob("add_alias_*.md"))
        ref = parse_refinement(fixture)
        target = skills_tree / ref["meta"]["target"]
        apply_refinement(ref)

        text = target.read_text()
        below_idx = text.index(self.MARKER_BELOW)
        above_idx = text.index(self.MARKER_ABOVE)
        # Body must appear between the two markers
        body_line = ref["body"].strip().splitlines()[0]
        body_pos = text.index(body_line)
        assert below_idx < body_pos < above_idx

    def test_missing_markers_raises(self, skills_tree, tmp_path):
        # Strip markers from the target
        target = skills_tree / "src/skills/netcdf-inspect/references/aliases.md"
        text = target.read_text()
        text = text.replace(self.MARKER_BELOW, "").replace(self.MARKER_ABOVE, "")
        target.write_text(text)

        fixture = next(FIXTURES_DIR.glob("add_alias_*.md"))
        ref = parse_refinement(fixture)
        with pytest.raises(Exception, match="marker"):
            apply_refinement(ref)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `pytest tests/tools/test_apply_refinements.py::TestAddAlias -v`

Expected: FAIL — current code raises `add_alias not implemented yet`.

- [ ] **Step 4: Implement `add_alias` in `tools/apply_refinements.py`**

Edit lines 96–98. Replace:

```python
    elif op == "add_alias":
        # TODO: parse table row from body, splice into aliases.md
        raise click.ClickException("add_alias not implemented yet")
```

With:

```python
    elif op == "add_alias":
        apply_marker_splice(target, body)
```

Add a new helper after `apply_replace_section`:

```python
MARKER_BELOW = "<!-- REFINER_INSERT_BELOW -->"
MARKER_ABOVE = "<!-- REFINER_INSERT_ABOVE -->"


def apply_marker_splice(target: Path, body: str) -> str:
    """Insert `body` into `target` between the REFINER_INSERT markers.

    The markers are HTML comments embedded in the markdown to delimit the
    auto-generated section. Used by add_alias and add_region operations.
    """
    text = target.read_text()
    if MARKER_BELOW not in text:
        raise click.ClickException(
            f"missing marker {MARKER_BELOW!r} in {target}; "
            f"file may not be in the canonical refiner-target format")
    if MARKER_ABOVE not in text:
        raise click.ClickException(
            f"missing marker {MARKER_ABOVE!r} in {target}")

    below_idx = text.index(MARKER_BELOW) + len(MARKER_BELOW)
    above_idx = text.index(MARKER_ABOVE)

    # Insert body just before the ABOVE marker, with surrounding whitespace
    inserted = body.strip() + "\n"
    new_text = (
        text[:below_idx]
        + "\n" + inserted
        + text[above_idx:]
    )
    target.write_text(new_text)
    return inserted
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/tools/test_apply_refinements.py::TestAddAlias -v`

Expected: PASS.

- [ ] **Step 6: Run the full suite**

Run: `pytest -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add tools/apply_refinements.py tests/tools/test_apply_refinements.py tests/tools/fixtures/refinements/add_alias_*.md
git commit -m "$(cat <<'EOF'
cycle-6 task 11: apply_refinements.add_alias op

apply_marker_splice locates the REFINER_INSERT_BELOW / _ABOVE marker
pair in the target and splices the draft body between them. Used by
add_alias (and reused by add_region in the next task).

Test fixtures derived from Phase A dogfood findings.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Implement `add_region` op (CONDITIONAL)

**Phase:** B. **Skip if Phase A produced zero findings that map to `add_region`.** Updates both `regions.md` (markdown table row, via marker splice) and `regions.json` (structured entry, via text-based splice with re-parse validation).

**Files:**
- Modify: `tools/apply_refinements.py:99-101`
- Modify: `tests/tools/test_apply_refinements.py` (add TestAddRegion class)
- Create: `tests/tools/fixtures/refinements/add_region_*.md`

- [ ] **Step 1: Create the fixture(s)**

Example fixture:

```markdown
---
target: src/skills/netcdf-plot-map/references/regions.md
operation: add_region
confidence: medium
evidence:
  - dogfood session 2026-05-08T19:01Z
  - user named "Gulf Stream extension" with bounds [-75, -45, 35, 45]
region_name: Gulf Stream extension
lon_min: -75
lon_max: -45
lat_min: 35
lat_max: 45
category: ocean_basin
notes: user-defined feature, not in standard atlases
---

| Gulf Stream extension | -75 | -45 | 35 | 45 |
```

The frontmatter carries the structured fields needed for the JSON insert; the body carries the markdown row for `regions.md`.

If Phase A had no findings, write a synthetic fixture.

- [ ] **Step 2: Write the failing test**

Add to `tests/tools/test_apply_refinements.py`:

```python
import json


class TestAddRegion:
    def test_md_row_inserted_between_markers(self, skills_tree):
        fixture = next(FIXTURES_DIR.glob("add_region_*.md"))
        ref = parse_refinement(fixture)
        md_target = skills_tree / "src/skills/netcdf-plot-map/references/regions.md"
        apply_refinement(ref)

        text = md_target.read_text()
        body_line = ref["body"].strip().splitlines()[0]
        below = text.index("<!-- REFINER_INSERT_BELOW -->")
        above = text.index("<!-- REFINER_INSERT_ABOVE -->")
        assert below < text.index(body_line) < above

    def test_json_entry_inserted_and_valid(self, skills_tree):
        fixture = next(FIXTURES_DIR.glob("add_region_*.md"))
        ref = parse_refinement(fixture)
        json_target = skills_tree / "src/skills/netcdf-plot-map/references/regions.json"
        apply_refinement(ref)

        # File must still parse as JSON
        data = json.loads(json_target.read_text())
        # New entry is in `regions` block under the proposed name
        name = ref["meta"]["region_name"]
        assert name in data["regions"]
        entry = data["regions"][name]
        assert entry["lon_min"] == ref["meta"]["lon_min"]
        assert entry["lon_max"] == ref["meta"]["lon_max"]
        assert entry["lat_min"] == ref["meta"]["lat_min"]
        assert entry["lat_max"] == ref["meta"]["lat_max"]

    def test_json_parse_failure_rolls_back(self, skills_tree, monkeypatch):
        """If the splice produces invalid JSON, the original file is preserved."""
        json_target = skills_tree / "src/skills/netcdf-plot-map/references/regions.json"
        original = json_target.read_text()

        # Force the JSON splice to produce invalid output by stubbing the
        # serializer to emit garbage
        from tools import apply_refinements as ar
        def bad_format(*args, **kwargs):
            return "{ not valid json"
        monkeypatch.setattr(ar, "_format_region_json_entry", bad_format)

        fixture = next(FIXTURES_DIR.glob("add_region_*.md"))
        ref = parse_refinement(fixture)
        with pytest.raises(Exception, match="JSON"):
            apply_refinement(ref)

        assert json_target.read_text() == original, (
            "JSON file was modified despite parse failure; rollback broken")
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `pytest tests/tools/test_apply_refinements.py::TestAddRegion -v`

Expected: FAIL — `add_region not implemented yet`.

- [ ] **Step 4: Implement `add_region` in `tools/apply_refinements.py`**

Edit lines 99–101. Replace:

```python
    elif op == "add_region":
        # TODO: parse region row, splice into regions.md AND regions.json
        raise click.ClickException("add_region not implemented yet")
```

With:

```python
    elif op == "add_region":
        # Markdown row goes into regions.md
        apply_marker_splice(target, body)
        # Structured entry goes into the sibling regions.json
        json_target = target.with_name("regions.json")
        if not json_target.exists():
            raise click.ClickException(f"sibling regions.json missing: {json_target}")
        apply_region_json_insert(json_target, meta)
```

Add helpers near `apply_marker_splice`:

```python
def _format_region_json_entry(meta: dict) -> str:
    """Format a regions.json entry as a single line preserving column shape."""
    name = meta["region_name"]
    fields = [
        f'"lon_min": {int(meta["lon_min"])}',
        f'"lon_max": {int(meta["lon_max"])}',
        f'"lat_min": {int(meta["lat_min"])}',
        f'"lat_max": {int(meta["lat_max"])}',
        f'"category": "{meta.get("category", "continental")}"',
    ]
    if "notes" in meta:
        fields.append(f'"notes": "{meta["notes"]}"')
    body = ", ".join(fields)
    return f'    "{name}": {{{body}}}'


def apply_region_json_insert(json_target: Path, meta: dict) -> None:
    """Splice a region entry into regions.json. Validates by re-parsing;
    rolls back the write if the result is not valid JSON.

    Insertion strategy: find the closing `}` of the `regions` block,
    insert a new line before it. Preserves column-aligned formatting.
    """
    original = json_target.read_text()
    new_entry = _format_region_json_entry(meta)

    # Find the regions block. We assume the file has a top-level "regions"
    # key followed by an opening `{`; insertion goes before the matching `}`.
    parsed = json.loads(original)
    if "regions" not in parsed:
        raise click.ClickException(f"{json_target}: no top-level 'regions' key")
    if meta["region_name"] in parsed["regions"]:
        raise click.ClickException(
            f"{json_target}: region {meta['region_name']!r} already exists")

    # Locate end of regions block: scan from `"regions": {` for matching brace
    start = original.index('"regions"')
    open_brace = original.index("{", start)
    depth = 0
    close_idx = -1
    for i in range(open_brace, len(original)):
        if original[i] == "{":
            depth += 1
        elif original[i] == "}":
            depth -= 1
            if depth == 0:
                close_idx = i
                break
    if close_idx < 0:
        raise click.ClickException(f"{json_target}: malformed regions block")

    # Insert "...,\n<new_entry>\n  " immediately before the closing brace.
    # Preserve trailing comma on the previous entry.
    before = original[:close_idx].rstrip()
    if not before.endswith(","):
        before = before + ","
    new_text = before + "\n" + new_entry + "\n  " + original[close_idx:]

    # Validate before writing
    try:
        json.loads(new_text)
    except json.JSONDecodeError as e:
        raise click.ClickException(
            f"{json_target}: splice produced invalid JSON ({e}); not writing")

    json_target.write_text(new_text)
```

Update `apply_refinement` to pass `meta` through. Locate the function signature:

```python
def apply_refinement(ref: dict) -> None:
    meta = ref["meta"]
    body = ref["body"]
    target_rel = meta["target"]
    target = REPO_ROOT / target_rel
```

Confirm `meta` is in scope — it already is. The `add_region` branch above references `meta` directly. No further wiring needed.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/tools/test_apply_refinements.py::TestAddRegion -v`

Expected: PASS.

- [ ] **Step 6: Run the full suite**

Run: `pytest -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add tools/apply_refinements.py tests/tools/test_apply_refinements.py tests/tools/fixtures/refinements/add_region_*.md
git commit -m "$(cat <<'EOF'
cycle-6 task 12: apply_refinements.add_region op

Markdown row spliced into regions.md via apply_marker_splice (reuses
the helper from add_alias). Structured entry inserted into sibling
regions.json via text-based splice that preserves column alignment;
re-parsed as JSON before commit; write rolls back if parse fails.

Test fixtures derived from Phase A dogfood findings.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Implement `set_config_default` op (CONDITIONAL)

**Phase:** B. **Skip if Phase A produced zero findings that map to `set_config_default`.** Edits the YAML frontmatter of a SKILL.md file via parsed round-trip.

**Files:**
- Modify: `tools/apply_refinements.py:102-104`
- Modify: `tests/tools/test_apply_refinements.py` (add TestSetConfigDefault class)
- Create: `tests/tools/fixtures/refinements/set_config_default_*.md`

- [ ] **Step 1: Create the fixture(s)**

Example fixture:

```markdown
---
target: src/skills/netcdf-plot-map/SKILL.md
operation: set_config_default
confidence: high
evidence:
  - dogfood session 2026-05-08T19:30Z
  - user said "use viridis for temperature plots from now on"
config_path: metadata.config.cmap.temperature
config_value: viridis
---

(no body — change is in frontmatter only)
```

Body may be empty for this op. The frontmatter `config_path` is dotted-key access; `config_value` is the new value. The applier must handle creation of intermediate dicts if the path doesn't fully exist.

If Phase A had no findings, write a synthetic fixture.

- [ ] **Step 2: Write the failing test**

Add to `tests/tools/test_apply_refinements.py`:

```python
import yaml


class TestSetConfigDefault:
    def test_sets_dotted_key_in_frontmatter(self, skills_tree):
        fixture = next(FIXTURES_DIR.glob("set_config_default_*.md"))
        ref = parse_refinement(fixture)
        target = skills_tree / ref["meta"]["target"]
        apply_refinement(ref)

        text = target.read_text()
        # Re-parse frontmatter
        m = parse_refinement.__globals__["FRONTMATTER_RE"].match(text)
        assert m, f"target {target} no longer has parseable frontmatter"
        fm = yaml.safe_load(m.group(1))
        # Walk the dotted path
        node = fm
        for part in ref["meta"]["config_path"].split("."):
            assert part in node, f"path {ref['meta']['config_path']} broken at {part}"
            node = node[part]
        assert node == ref["meta"]["config_value"]

    def test_body_preserved_verbatim(self, skills_tree):
        fixture = next(FIXTURES_DIR.glob("set_config_default_*.md"))
        ref = parse_refinement(fixture)
        target = skills_tree / ref["meta"]["target"]
        original_body = target.read_text().split("---", 2)[2]
        apply_refinement(ref)
        new_body = target.read_text().split("---", 2)[2]
        assert original_body == new_body, (
            "set_config_default modified the SKILL.md body; should only "
            "touch frontmatter")
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `pytest tests/tools/test_apply_refinements.py::TestSetConfigDefault -v`

Expected: FAIL — `set_config_default not implemented yet`.

- [ ] **Step 4: Implement `set_config_default` in `tools/apply_refinements.py`**

Edit lines 102–104. Replace:

```python
    elif op == "set_config_default":
        # TODO: edit YAML frontmatter
        raise click.ClickException("set_config_default not implemented yet")
```

With:

```python
    elif op == "set_config_default":
        config_path = meta.get("config_path")
        if not config_path:
            raise click.ClickException(
                "set_config_default requires `config_path` in frontmatter")
        config_value = meta.get("config_value")
        apply_set_config_default(target, config_path, config_value)
```

Add a new helper:

```python
def apply_set_config_default(target: Path, config_path: str, value) -> None:
    """Edit the YAML frontmatter of `target` to set the dotted-path key.

    Creates intermediate dicts if missing. Body content preserved verbatim.
    """
    text = target.read_text()
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise click.ClickException(
            f"{target}: no parseable YAML frontmatter; cannot apply "
            f"set_config_default")
    fm_text = m.group(1)
    body = m.group(2)
    fm = yaml.safe_load(fm_text) or {}

    # Walk / create the dotted path
    parts = config_path.split(".")
    node = fm
    for part in parts[:-1]:
        if part not in node or not isinstance(node[part], dict):
            node[part] = {}
        node = node[part]
    node[parts[-1]] = value

    new_fm = yaml.safe_dump(fm, sort_keys=False, default_flow_style=False)
    target.write_text("---\n" + new_fm + "---\n" + body)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/tools/test_apply_refinements.py::TestSetConfigDefault -v`

Expected: PASS.

- [ ] **Step 6: Run the full suite**

Run: `pytest -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add tools/apply_refinements.py tests/tools/test_apply_refinements.py tests/tools/fixtures/refinements/set_config_default_*.md
git commit -m "$(cat <<'EOF'
cycle-6 task 13: apply_refinements.set_config_default op

apply_set_config_default edits the YAML frontmatter of a SKILL.md via
yaml.safe_load / yaml.safe_dump round-trip. Body content preserved
verbatim. Dotted-key path syntax with auto-creation of intermediate
dicts.

Test fixtures derived from Phase A dogfood findings.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Update unimplemented-op error messages

**Phase:** B (always ships).

For each of `replace_section`, `add_alias`, `add_region`, `set_config_default` that did NOT ship in cycle 6 (i.e. Tasks 10–13 that were skipped), update the `ClickException` message to name the cycle that should complete the op rather than just "not implemented yet."

**Files:**
- Modify: `tools/apply_refinements.py:93-104` (only the branches still raising `ClickException`)

- [ ] **Step 1: For each unshipped op, update the message**

For example, if `add_region` was NOT shipped this cycle:

```python
    elif op == "add_region":
        raise click.ClickException(
            "add_region: not implemented in cycle 6 (no Phase-A finding "
            "justified shipping it). Track for cycle 7+ scope.")
```

Apply this pattern to each unshipped branch. Skip branches that DID ship in Tasks 10–13.

If ALL applier ops shipped, this task is a no-op — verify no `not implemented yet` messages remain:

```bash
grep -n "not implemented yet" tools/apply_refinements.py
```

If empty, skip the commit.

- [ ] **Step 2: Run the suite to ensure no regression**

Run: `pytest -q`

Expected: PASS.

- [ ] **Step 3: Commit (only if any messages were updated)**

```bash
git add tools/apply_refinements.py
git commit -m "$(cat <<'EOF'
cycle-6 task 14: name cycle 7+ as deadline for unshipped applier ops

For applier operations that didn't get a Phase-A finding to justify
shipping in cycle 6, the ClickException message now names cycle 7+ as
the tracking scope rather than the bare 'not implemented yet' from
the cycle-5 scaffold.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: Final gate

**Phase:** B (always ships). The gate that proves cycle 6 is complete.

- [ ] **Step 1: Build every target and confirm payload integrity**

```bash
python -m tools.build claude-code
python -m tools.build claude-desktop
python -m tools.build codex
python -m tools.build cursor
python -m tools.build copilot
python -m tools.build gemini-cli
python -m tools.build antigravity
python -m tools.build hermes
```

Expected: every command exits 0.

- [ ] **Step 2: Verify skill-refiner is in every payload**

```bash
for host in claude-code claude-desktop codex cursor copilot gemini-cli antigravity; do
  test -f "build/$host/metplot/skills/skill-refiner/SKILL.md" \
    || test -f "build/$host/metplot/.agent/skills/skill-refiner/SKILL.md" \
    && echo "$host: ok" || echo "$host: MISSING"
done
```

Expected: every host prints `ok`.

- [ ] **Step 3: Run the full suite + lint + types**

```bash
pytest -ra
ruff check
mypy .
```

Expected: all green.

- [ ] **Step 4: Re-run the dogfood install steps to confirm Claude Code Stop hook fires**

This is manual verification (no CI harness for live host hooks). Steps:

1. `cp -r build/claude-code/metplot ~/.claude/plugins/metplot`
2. Restart Claude Code.
3. In a new session: run a few plot tasks, make at least one correction.
4. End the session.
5. Check `.metplot/refinements/` — at least one draft should exist (or zero with a clean exit if no signal).

If the Stop hook produced drafts, optionally run `metplot-refine --list` to confirm the applier sees them.

- [ ] **Step 5: Commit (gate marker)**

If anything was modified during the gate (e.g. lint fix, mypy fix), commit it now:

```bash
git add -A
git commit -m "$(cat <<'EOF'
cycle-6 task 15: final gate — all builds + suite + lint + mypy green

Every target builds; skill-refiner ships everywhere; pytest, ruff,
and mypy are green. Manual verification confirmed the Claude Code
Stop hook fires and produces drafts under .metplot/refinements/
when the session contained signal.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

If nothing changed, this task is a verification-only no-op — no commit needed.

---

## Self-review checklist (run after the plan is written)

**Spec coverage** (every numbered requirement in the spec maps to a task):

| Spec requirement | Task |
|---|---|
| §1 Phase A: dogfood findings doc | Task 1 |
| §1 Phase A success criteria evaluated post-"enough" | Plan-revision checkpoint |
| §1 Phase B: skill-refiner in `INCLUDED_SKILLS` | Task 2 |
| §1 Phase B: Claude Code real `/refine` | Task 4 |
| §1 Phase B: Claude Code Stop hook | Task 5 |
| §1 Phase B: other-host `/refine` updated | Task 6 |
| §1 Phase B: Codex/Claude Desktop README | Task 7 |
| §1 Phase B: applier ops dogfood-justified | Tasks 10–13 (conditional) |
| §1 Phase B: unimplemented-op deadline | Task 14 |
| §1 Phase B: full suite + lint + mypy green | Task 15 |
| §2.1 findings doc with six categories | Task 1 |
| §3.1 source-of-truth code (3 files) | Tasks 2, 8, 10–13 |
| §3.2 per-target build wiring | Tasks 4, 5, 6, 7 |
| §3.3 cross-host smoke test | Task 3 |
| §3.3 Claude Code refine + stop tests | Tasks 4, 5 |
| §3.3 fixtures derived from Phase A | Tasks 10–13 |
| §3.4 docs (README, architecture.md, self-improvement.md, target READMEs) | Task 9 |
| §4 cross-cutting principles (TDD, allowlist first, splice markers, etc.) | Honored across Tasks 2 → 15 |
| §5 open risk: regions.json fragility | Task 12 (re-parse-validates) |
| §5 open risk: Phase A no signal | Plan-revision checkpoint + Task 14 |
| §5 open risk: missing category | Plan-revision checkpoint + Task 8 |

No gaps.

**Placeholder scan** (red flags from the writing-plans guidance):

- "TBD" / "TODO": none in plan body. (Tasks 10–13 contain "(if zero findings, write synthetic fixture)" — concrete instruction, not a placeholder.)
- "Add appropriate error handling": none.
- "Similar to Task N": Tasks 6b/c/d explicitly reference 6a's pattern AND repeat the steps with full file paths and code; this is the "repeat the code" path the guidance prefers. Acceptable.
- "Implement later": only in Task 14, which is exactly the cycle 7+ deferral mechanism — that's intentional and the spec calls for it.

**Type consistency:**

- `apply_marker_splice(target, body)` defined in Task 11, reused in Task 12. Signature consistent.
- `_format_region_json_entry(meta)` defined in Task 12, referenced in Task 12's monkeypatch test. Consistent.
- `apply_replace_section`, `apply_set_config_default` defined and called by name. Consistent.
- `MARKER_BELOW`, `MARKER_ABOVE` module-level constants defined in Task 11, used in Tasks 11 and 12. Consistent.

No issues.
