# Slash command namespacing — survey (May 2026)

Focused research before designing cycle 5's `/setup` and cycle 6's
`/refine` commands. Question: how do plugin slash commands get
namespaced across the 5 slash-capable hosts?

## At-a-glance

| Host | Invoke syntax | Namespace source | Customizable? | Conflict resolution |
|------|---------------|------------------|---------------|---------------------|
| **Claude Code** | `/plugin-name:skill-name` (from plugin); bare `/skill-name` for personal skills | `name` field in `plugin.json` | **No** — locked to manifest name | Plugin skills isolated by prefix; never collide with personal/project skills |
| **Codex CLI** | `/command` (bare) for built-ins / user custom prompts; plugin-provided slash commands undocumented | Filename in `~/.codex/commands/` for user commands | unconfirmed | unconfirmed |
| **Gemini CLI** | `/command` or `/dir:command` (subdirectory → colon namespace) | File path relative to `.gemini/commands/` | **No** — derived from directory/filename | Project-scoped overrides user-scoped (project wins) |
| **Cursor** | `/command-name` (bare) | `name` field in command file frontmatter; fallback to filename | No documented alias / prefix mechanism | unconfirmed |
| **GitHub Copilot** | `/plugin-name:skill-name` (auto-prefixed); bare `/skill-name` for standalone skills | `name` field in `plugin.json` is prefix; skill `name` is suffix | **No** — manually adding colons causes silent load failures | unconfirmed for slash commands; bare-name collisions are a known open issue (copilot-cli #2898) |

## Quick takeaways

1. **Claude Code** and **Copilot** are the only hosts that actually
   namespace plugin commands automatically. Both derive the prefix
   verbatim from the manifest `name` field.
2. **Gemini CLI** namespaces by subdirectory; **Cursor** uses bare
   names with no plugin-level isolation; **Codex** plugin command
   syntax is undocumented (likely bare).
3. To get `/ncplot:setup` instead of `/ncplot-agent:setup` on Claude
   Code and Copilot, the manifest `name` must be `ncplot` (no alias
   mechanism exists). Other hosts can independently use `/ncplot:`
   via Gemini's subdirectory pattern; Cursor + Codex stay bare.

## Sources

- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/plugins-reference
- https://geminicli.com/docs/cli/custom-commands/
- https://cursor.com/docs/plugins/building
- https://github.com/cursor/plugins
- https://code.visualstudio.com/docs/copilot/customization/agent-skills
- https://code.visualstudio.com/docs/copilot/customization/agent-plugins
- https://github.com/github/copilot-cli/issues/2898
- https://developers.openai.com/codex/cli/slash-commands
