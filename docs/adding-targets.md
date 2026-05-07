# Adding a new target

A target is a build adapter that turns the canonical `src/` content into a
plugin format consumable by a specific agent host.

## Minimum requirements

Create `targets/<name>/build.py` exposing:

```python
def build(src_root: Path, out_root: Path) -> None:
    """Build the plugin into out_root/<name>/."""
```

Then register it in `tools/build.py`'s `TARGETS` dict.

## What `build()` must do

1. Read every skill from `src_root / "skills"`.
2. Translate them into the target's skill format (often a no-op — SKILL.md
   is already widely supported).
3. Emit the target's manifest / config file describing skills, MCP servers,
   slash commands, and hooks as appropriate.
4. Copy MCP server source from `src_root / "mcp"` and emit launch-command
   stanzas pointing at it.
5. Optionally emit a README with install instructions.

## Reference implementations

- `targets/claude-code/build.py` — full plugin with hooks (the reference)
- `targets/claude-desktop/build.py` — MCP-only, since Desktop has no
  native skill loader; skill content is concatenated into a project doc
- `targets/hermes/build.py` — near-identity copy; format is already
  compatible
- `targets/codex/build.py` — emits AGENTS.md and a setup script

## Skill-format compatibility matrix

| Field/feature           | Claude Code | Hermes | Cursor | Codex (AGENTS.md) |
|-------------------------|-------------|--------|--------|-------------------|
| YAML frontmatter        | yes         | yes    | yes    | concatenated      |
| `references/`           | yes         | yes    | yes    | inlined           |
| `scripts/`              | yes         | yes    | yes    | bundled separately|
| Slash commands          | yes         | yes    | no     | no                |
| Hooks                   | yes         | yes    | limited| no                |
| MCP                     | yes         | yes    | yes    | via SDK           |

When a feature isn't supported by a target, `build.py` is responsible for
either degrading gracefully (e.g. concatenating skill bodies into a single
context document) or omitting the feature with a warning.
