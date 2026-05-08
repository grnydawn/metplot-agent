# Multi-host porting research for ncplot-agent (May 2026)

Survey of plugin / skill / extension models across the major AI coding
hosts, conducted before opening cycle 7. Source: web search + official
docs of each host.

## At-a-glance comparison

| Host | Skill format | MCP | Slash cmds | Hooks | Distribution | Porting effort |
|------|-------------|-----|-----------|-------|--------------|----------------|
| **Claude Code** (baseline) | `skills/<name>/SKILL.md` (YAML frontmatter + md body) | yes, stdio, `.mcp.json` | yes, `commands/<name>.md` | yes, `settings.json` (PreToolUse, PostToolUse, Stop, etc.) | plugin dir / marketplace | **DONE (cycle 4)** |
| **Claude Desktop** | concatenated project instructions doc (no native skill loader) | yes, stdio, `claude_desktop_config.json` | no | no | `.mcpb` bundle (MCP-only) | **trivial** (stub already exists) |
| **Codex CLI** | `skills/<name>/SKILL.md`, `.agents/skills/` | yes, stdio, `~/.codex/config.toml` | yes (built-in catalog; user-invocable skills surface as `/foo`) | yes, `[hooks]` in `config.toml` | `.codex-plugin/plugin.json`, OpenAI marketplace | **moderate** (1–2 days) |
| **Codex Desktop** | same as Codex CLI (shared plugin format) | same `.mcp.json` stanza | same | yes, `hooks/hooks.json` | same marketplace | **moderate** (shared with CLI) |
| **Gemini CLI** | `skills/<name>/SKILL.md`, `.gemini/skills/` or `.agents/skills/` | yes, stdio, `settings.json` | yes, `commands/<name>.toml` | yes, `settings.json` hooks (12+ events) | `gemini-extension.json` bundle, `gemini extensions install <git-url>` | **moderate** (1–2 days) |
| **Antigravity** | `skills/<name>/SKILL.md`, `.agent/skills/` (project) or `~/.gemini/antigravity/skills/` (global) | yes, stdio, `mcp_config.json` | yes (workflows: `.agent/workflows/<name>.md`) | **no formal hook system** (Workflows/Rules only) | unconfirmed registry; manual copy | **moderate** (1 day; no hooks) |
| **Cursor** | `skills/<name>/SKILL.md`, `.cursor/skills/` | yes, stdio, `.cursor/mcp.json` | yes, `commands/` dir in plugin | yes, `.cursor/hooks.json` (camelCase events) | `.cursor-plugin/plugin.json`, Cursor Marketplace | **moderate** (1–2 days) |
| **GitHub Copilot** | `skills/<name>/SKILL.md`, `.github/skills/` or `.agents/skills/` | yes, stdio, `.vscode/mcp.json` (uses `servers` key, not `mcpServers`) | yes (skills with `user-invocable: true` surface as `/`) | yes, `.github/hooks/*.json` (PascalCase events) | `plugin.json`, VS Code extensions view | **moderate** (1–2 days) |

---

## Project being ported

`ncplot-agent` is a multi-target plugin currently shipping for Claude
Code (cycle 4 merged 2026-05-08). Source consists of:

1. **5 skills** — markdown files with YAML frontmatter
2. **2 MCP servers** — `netcdf-reader` (8 tools) and `plot-renderer`
   (3 tools), Python packages with entry-point scripts
3. **Optional** `/refine` slash command (placeholder for cycle 6) and
   (future) Stop hook for self-improvement

Distribution: per-host build target in `targets/<name>/build.py` that
packages the canonical L1 source into the host's expected layout.

For Claude Code (cycle 4), the plugin payload is:
```
.claude-plugin/plugin.json    # manifest
skills/<name>/SKILL.md        # 5 skills
mcp-servers/<name>/           # installable Python packages
.mcp.json                     # MCP launch stanzas
commands/refine.md            # slash command
```

The build is `python -m tools.build claude-code`.

---

## Claude Desktop

**Skill format.** No native skill loader. The current
`targets/claude-desktop/build.py` already handles this correctly: it
concatenates all five skill bodies (stripping YAML frontmatter) into a
single `project_instructions.md` and tells the user to paste it into a
Claude Project's knowledge area. YAML frontmatter is lost, but the
markdown bodies are fully preserved.

**MCP.** Full stdio MCP support via `claude_desktop_config.json`
(macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`).
Entry-point scripts (`ncplot-netcdf-reader`, `ncplot-plot-renderer`)
are callable by name once `pip install`ed. The stub build emits the
correct `mcp_config_snippet.json`.

**Slash commands.** Not supported in Claude Desktop's chat UI. The
`/refine` command degrades to a manual prompt.

**Hooks.** No hook system exists in Claude Desktop. The Stop hook /
skill-refiner closed loop is unavailable; refinement must be triggered
manually.

**Distribution.** The `.mcpb` (formerly `.dxt`) bundle format packages
a single MCP server with its dependencies as a ZIP archive with a
`manifest.json`. This is specifically for MCP-server distribution, not
for skills or instruction files. For ncplot-agent the full integration
still requires the project-instructions paste step. A future cycle
could package the two MCP servers as `.mcpb` files for one-click
install, with a separate manual step for skills.

**Porting effort: trivial.** The stub `targets/claude-desktop/build.py`
already produces a working artifact. Outstanding work: (1) add explicit
`python -m` fallback in the MCP launch stanza (the current build
hard-codes `server.py` paths rather than using the installed
entry-points), (2) optionally package each MCP server as a `.mcpb`
bundle. This is an afternoon of cleanup, not a new build.

---

## Codex CLI

**Skill format.** Codex uses an identical `SKILL.md` convention to
Claude Code: a directory named after the skill containing a `SKILL.md`
file with `name` / `description` YAML frontmatter and a markdown body.
Skills are discovered from `.agents/skills/` (project-root),
`$HOME/.agents/skills/` (user), and `/etc/codex/skills` (admin). This
is the same `.agents/skills/` interop path that Gemini CLI and Copilot
also watch — meaning the same skill directories can be shared across
all three. An optional `agents/openai.yaml` file inside the skill
directory adds UI metadata and an explicit invocation policy.

**MCP.** Full stdio MCP support. Config lives in `~/.codex/config.toml`
(global) or `.codex/config.toml` (project). TOML format:
```toml
[mcp_servers.netcdf-reader]
type = "stdio"
command = "ncplot-netcdf-reader"
args = []
```
The existing entry-point scripts are directly usable.

**Slash commands.** Codex has ~40 built-in slash commands. Custom
slash-command authoring via a file format is not documented in the
official CLI reference — the documented customization is through
skills (which can be user-invocable with `/skill-name`) and `AGENTS.md`.
The `/refine` command would degrade to a skill invocable as `$refine`
or described in AGENTS.md context.

**Hooks.** Full hook support under `[hooks]` in `config.toml` (or
`hooks.json`). Supported events: `PreToolUse`, `PostToolUse`,
`PermissionRequest`, `SessionStart`, `UserPromptSubmit`, `Stop`. The
Stop hook for the skill-refiner closed loop (cycle 6) would work here.

**Distribution.** Plugin format: `.codex-plugin/plugin.json` manifest
at the plugin root. Components: `skills/`, `.mcp.json`,
`hooks/hooks.json`, `.app.json`. Published to the OpenAI Codex
marketplace (launched March 2026, 90+ plugins at launch). The manifest
format is very close to the Claude Code `.claude-plugin/plugin.json` —
both require `name`, support `version`, `description`, `author`, and
have component pointers.

**Porting effort: moderate.** The existing AGENTS.md-concatenation
stub in `targets/codex/build.py` is now out of date — Codex has native
`SKILL.md` support. The real work is: (1) write a new
`targets/codex/build.py` that mirrors the Claude Code build (emit
`.codex-plugin/plugin.json`, copy skills to `skills/`, write
`config.toml` MCP stanzas instead of `.mcp.json`), (2) translate hook
event names (identical schema to Claude Code), (3) drop the AGENTS.md
concatenation in favour of native skill discovery. Estimated 1–2 days
to produce and test a clean Codex plugin build.

---

## Codex Desktop

**Relationship to Codex CLI.** Codex Desktop (released v26.415, April
2026) shares the same plugin format and skill system as Codex CLI.
Plugins are `.codex-plugin/plugin.json` bundles; skills, MCP servers,
hooks, and app connectors are all the same. The desktop app
additionally supports background computer-use agents and the 90+
marketplace plugins, but the configuration and extension surfaces are
identical.

**Porting effort: moderate (shared with CLI target).** The Codex CLI
target build, once written, produces an artifact that installs
identically in Codex Desktop. No separate `targets/codex-desktop/build.py`
is needed — a single `targets/codex/build.py` covers both. The
"Desktop" column in the table is effectively free once the CLI target
is done.

---

## Gemini CLI

**Skill format.** Gemini CLI uses the same `SKILL.md` convention (YAML
frontmatter with `name` and `description`, markdown body, optional
`references/`/`scripts/`/`assets/` subdirs). Discovery paths: built-in
→ extension skills → `~/.gemini/skills/` (or `~/.agents/skills/`) →
`.gemini/skills/` (or `.agents/skills/`). The `.agents/skills/` path
is an explicit interop alias that Gemini CLI, Codex, and Copilot all
share. Skill activation is triggered automatically when task
description matches, or explicitly via `gemini skills activate <name>`.
Distribution: `gemini skills install https://github.com/user/repo.git`.

**MCP.** Full stdio MCP support. Config in `settings.json` (project:
`.gemini/settings.json`, user: `~/.gemini/settings.json`). Supports
`command`/`args` for stdio, `url` for SSE, `httpUrl` for Streamable
HTTP. Entry-point scripts work directly.

**Slash commands.** Custom commands are `.toml` files in
`.gemini/commands/` (project) or `~/.gemini/commands/` (user). Format:
```toml
description = "Review the current session and propose skill refinements"
prompt = "Run the skill-refiner against the current session log..."
```
The `/refine` command maps directly to `.gemini/commands/refine.toml`.

**Hooks.** Hook system in `settings.json` under `hooks` key. Events:
`BeforeTool`, `AfterTool`, `BeforeAgent`, `AfterAgent`, `BeforeModel`,
`AfterModel`, `BeforeToolSelection`, `SessionStart`, `SessionEnd`,
`Notification`, `PreCompress`. Each hook runs a shell command;
communication via stdin/stdout JSON. The `SessionEnd` hook replaces
the Claude Code `Stop` hook for the skill-refiner cycle 6 trigger.

**Distribution.** Extensions are directories with a
`gemini-extension.json` manifest, installable from a GitHub URL via
`gemini extensions install`. The manifest can include `mcpServers`,
`contextFileName`, `skills/` subdirectory, and `hooks/hooks.json`.
This is the cleanest distribution unit for ncplot-agent on Gemini CLI.

**Note.** As of March 2026, Google is deprecating eager-loaded MCP
servers inside extensions in favour of skill-based discovery. The MCP
servers still work; they just should not be eagerly loaded on
extension install.

**Porting effort: moderate.** Skill files are directly portable (YAML
frontmatter is identical). Work needed: (1) write `gemini-extension.json`
manifest, (2) translate MCP stanzas from `.mcp.json` →
`settings.json` format, (3) write `commands/refine.toml` (trivial),
(4) write `hooks/hooks.json` with `SessionEnd` → skill-refiner trigger
(same logic as the Stop hook for cycle 6). Estimated 1–2 days.

---

## Antigravity

**Skill format.** Antigravity uses `SKILL.md` with the same
`name`/`description` YAML frontmatter. Project-scope path:
`.agent/skills/<name>/SKILL.md`. Global path:
`~/.gemini/antigravity/skills/<name>/SKILL.md`. The format is
identical to Claude Code's — optional `references/`, `scripts/`,
`examples/`, `assets/` subdirs are supported. Antigravity v1.20.3+
also recognises `AGENTS.md` in the project root as a cross-tool
compatibility layer.

**MCP.** Full stdio MCP support. Config accessed via Agent Panel →
MCP Servers → "View raw config", which opens `mcp_config.json`
(filesystem path not publicly documented; likely
`~/.gemini/antigravity/mcp_config.json` on macOS/Linux). JSON format
with `mcpServers` object, same structure as Claude Desktop's
`claude_desktop_config.json`. Entry-point scripts work; `${VAR_NAME}`
substitution is supported in env values (v1.20.x+).

**Slash commands / Workflows.** Workflows are markdown files in
`.agent/workflows/<name>.md` with YAML frontmatter (`description`).
Typing `/deploy` triggers `.agent/workflows/deploy.md`. This is the
analog of Claude Code's `commands/<name>.md` but with full markdown
body rather than a frontmatter-only description. The `/refine`
command maps to `.agent/workflows/refine.md`.

**Hooks.** No formal hook event system has been confirmed in official
Antigravity documentation. The community workaround is using Rules
(`.agent/rules/`) for behavioral policies and Workflows for triggered
automation. Formal lifecycle hooks (PreToolUse, SessionEnd, etc.)
appear to be a frequently requested but unimplemented feature as of
May 2026. The Stop hook for the skill-refiner closed loop is **not
available**.

**Distribution.** No official plugin marketplace or registry
confirmed. Community repos (e.g., antigravity.codes,
github.com/guanyang/antigravity-skills) serve as informal catalogs.
Installation is manual copy to `.agent/skills/` or the global path.

**Porting effort: moderate.** Skill files are directly portable. Work
needed: (1) write `targets/antigravity/build.py` that copies skills
to `.agent/skills/`, writes `mcp_config.json` snippet, writes
`.agent/workflows/refine.md`, (2) note that the Stop hook /
skill-refiner closed loop (cycle 6) must degrade to a manual workflow
invocation. The absence of hooks is the main functional gap. Estimated
1 day for the build script; the hook degradation is a design
constraint, not extra code.

---

## Cursor

**Skill format.** Cursor plugins use `skills/<name>/SKILL.md` with
`name`/`description` YAML frontmatter — identical to Claude Code's
format. Skills are discovered from `.cursor/skills/` in the project.
Agents pick up skills automatically. The plugin manifest is
`.cursor-plugin/plugin.json`.

**MCP.** Full stdio MCP support. Config: `.cursor/mcp.json` (project)
or user settings. Format: `{ "mcpServers": { "name": { "command":
"...", "args": [...] } } }` — same structure as `.mcp.json`.
Entry-point scripts are directly usable. One-click install of popular
MCP servers from Cursor's curated collection is available.

**Slash commands.** Commands live in a `commands/` directory within
the plugin, as `.md`/`.mdc`/`.txt` files with YAML frontmatter. Legacy
slash commands are deprecated in favour of the skills system; a skill
with `user-invocable: true` surfaces in the `/` menu. The `/refine`
command maps to either a `commands/refine.md` or a skill with
`user-invocable: true`.

**Hooks.** Cursor uses `.cursor/hooks.json` with camelCase event names
(`sessionStart`, `preToolUse`, `postToolUse`, `stop`,
`beforeSubmitPrompt`, plus `subagentStart`/`subagentStop`). The Stop
hook for the skill-refiner closed loop (cycle 6) will work. Hook
commands start 40x faster than earlier Cursor versions per the May
2026 release notes.

**Distribution.** `.cursor-plugin/plugin.json` manifest; published to
the Cursor Marketplace (launched alongside Cursor's marketplace blog
post). Plugins can also be installed locally via path config.

**Porting effort: moderate.** The plugin layout is nearly identical
to Claude Code: same `SKILL.md` format, same MCP JSON structure, same
hook semantics (just different event name casing). Work: (1) write
`targets/cursor/build.py` that emits `.cursor-plugin/plugin.json`,
copies skills, writes `.cursor/mcp.json`, writes `hooks/hooks.json`
with camelCase events. The manifest schema differs from Claude Code
but both are simple JSON. Estimated 1–2 days.

---

## GitHub Copilot (VS Code)

**Skill format.** Copilot agent skills use `SKILL.md` with
`name`/`description` YAML frontmatter (max 64 char name, max 1024 char
description). Additional optional frontmatter: `argument-hint`,
`user-invocable`, `disable-model-invocation`, `context`. Discovery
paths: `.github/skills/`, `.claude/skills/`, `.agents/skills/`
(project); `~/.copilot/skills/`, `~/.claude/skills/`,
`~/.agents/skills/` (user). The `.agents/skills/` path again serves
as the cross-tool interop path. Plugin manifest: `plugin.json`.

**MCP.** Full stdio MCP support. Config: `.vscode/mcp.json` (project)
or user profile (via VS Code settings). Format: `{ "servers": { "name":
{ "command": "...", "args": [...] } } }` — note: `servers` key (not
`mcpServers`). Entry-point scripts are supported. The MCP config key
name differs from every other host.

**Slash commands.** Skills with `user-invocable: true` (default)
surface as `/` commands. There is also a `commands/` directory within
a plugin for dedicated slash commands. The built-in `/create-skill`,
`/create-hook`, etc. commands scaffold new customizations. The
`/refine` command maps naturally.

**Hooks.** `hooks.json` at `.github/hooks/` (project) or
`~/.copilot/hooks/` (user), or inline in `plugin.json`. Supported
events: `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`,
`PreCompact`, `SubagentStart`, `SubagentStop`, `Stop`. The `Stop`
event is the cycle-6 skill-refiner trigger. Copilot also reads
`.claude/settings.json` as an alternative hooks source (cross-tool
compatibility).

**Distribution.** `plugin.json` manifest; install from VS Code
extensions view (search `@agentPlugins`), from the Awesome Copilot
marketplace (`copilot plugin install <name>@awesome-copilot`), or from
a Git URL via "Chat: Install Plugin From Source". Currently in
Preview. The plugin system also works in the Copilot CLI.

**Porting effort: moderate.** Skill files are directly portable. Key
differences from Claude Code: (1) `plugin.json` is at the plugin root
(not in `.claude-plugin/`), (2) MCP config uses `servers` key instead
of `mcpServers`, (3) hooks event names are PascalCase
`Stop`/`PreToolUse` — same as Claude Code. Work: write
`targets/copilot/build.py` that produces `plugin.json`, copies skills
to `skills/`, writes `.vscode/mcp.json` with `servers` key, writes
`hooks/hooks.json`. Estimated 1–2 days; the `servers` vs `mcpServers`
difference is the main trap.

---

## Recommended porting order

**1. Codex CLI + Desktop (shared target) — next sprint.**
The skill format is identical to Claude Code, the hook schema is the
same, and the plugin manifest is structurally similar. The existing
AGENTS.md stub should be replaced with a proper native-skill build.
One target covers both Codex CLI and Desktop. User reach is
substantial (OpenAI's user base + VS Code IDE integration).

**2. Gemini CLI — second.**
Direct skill portability, richest hook system outside Claude Code (12
events including `SessionEnd`), clean extension distribution via a
Git URL. The `/refine` command drops to a `.toml` file. This is the
most technically complete non-Anthropic target.

**3. Cursor — third.**
Near-identical layout to Claude Code. The only real friction is the
camelCase hook event names and the separate marketplace submission
step. High user reach in the AI-editor segment.

**4. GitHub Copilot — fourth.**
Skill format is identical; the `servers` vs `mcpServers` key in the
MCP config is the main gotcha. Plugin system is still in Preview as
of May 2026, so some roughness should be expected. Very high user
reach (VS Code default distribution).

**5. Antigravity — fifth.**
Skill format works. MCP works. No hook system means cycle-6
self-improvement degrades to a manual workflow. Worth doing once the
higher-reach targets are stable; the user base is growing but smaller
than Cursor/Copilot.

**6. Claude Desktop — whenever the `.mcpb` packaging is wanted.**
The stub already works for the core use case. Upgrading to `.mcpb`
bundles is a polish step, not a functional gap.

---

## Confidence notes

- Antigravity's `mcp_config.json` exact filesystem path is unconfirmed
  from official docs; derived from community tutorials.
- Antigravity hook system: officially unconfirmed; absence of formal
  hooks is consistent across multiple community and official sources
  checked.
- Codex CLI custom slash-command authoring (user-defined `/foo` via
  file): not confirmed in official docs; skills with `user-invocable`
  frontmatter appear to be the intended mechanism.
- Cursor plugin marketplace schema details were from the official
  `cursor.com/docs/plugins/building` page; the marketplace itself
  launched alongside the blog post and is relatively new.
- GitHub Copilot agent plugins are still in Preview as of May 2026.

---

## Sources

- [Agent Skills – Codex | OpenAI Developers](https://developers.openai.com/codex/skills)
- [Model Context Protocol – Codex | OpenAI Developers](https://developers.openai.com/codex/mcp)
- [Custom instructions with AGENTS.md – Codex | OpenAI Developers](https://developers.openai.com/codex/guides/agents-md)
- [Configuration Reference – Codex | OpenAI Developers](https://developers.openai.com/codex/config-reference)
- [Build plugins – Codex | OpenAI Developers](https://developers.openai.com/codex/plugins/build)
- [Slash commands in Codex CLI | OpenAI Developers](https://developers.openai.com/codex/cli/slash-commands)
- [Gemini CLI extensions | Gemini CLI](https://geminicli.com/docs/extensions/)
- [Extension reference | Gemini CLI](https://geminicli.com/docs/extensions/reference/)
- [MCP servers with Gemini CLI | Gemini CLI](https://geminicli.com/docs/tools/mcp-server/)
- [Agent Skills | Gemini CLI](https://geminicli.com/docs/cli/skills/)
- [Gemini CLI hooks reference](https://geminicli.com/docs/hooks/reference/)
- [Custom commands | Gemini CLI](https://geminicli.com/docs/cli/custom-commands/)
- [Cursor – Model Context Protocol (MCP) docs](https://docs.cursor.com/context/model-context-protocol)
- [Extend Cursor with plugins | Cursor](https://cursor.com/blog/marketplace)
- [Plugins Reference | Cursor Docs](https://cursor.com/docs/plugins/building)
- [Subagents, Skills, and Image Generation · Cursor changelog](https://cursor.com/changelog/2-4)
- [Agent plugins in VS Code (Preview)](https://code.visualstudio.com/docs/copilot/customization/agent-plugins)
- [Use Agent Skills in VS Code](https://code.visualstudio.com/docs/copilot/customization/agent-skills)
- [Agent hooks in Visual Studio Code (Preview)](https://code.visualstudio.com/docs/copilot/customization/hooks)
- [Add and manage MCP servers in VS Code](https://code.visualstudio.com/docs/copilot/customization/mcp-servers)
- [Extending GitHub Copilot Chat with MCP servers](https://docs.github.com/copilot/customizing-copilot/using-model-context-protocol/extending-copilot-chat-with-mcp)
- [One-click MCP server installation for Claude Desktop | Anthropic](https://www.anthropic.com/engineering/desktop-extensions)
- [Build with Google Antigravity | Google Developers Blog](https://developers.googleblog.com/build-with-google-antigravity-our-new-agentic-development-platform/)
- [Antigravity Skills Setup Guide (2026) | Antigravity.codes](https://antigravity.codes/blog/antigravity-skills-setup-guide)
- [How to Use MCP Servers in Antigravity (2026) | Antigravity.codes](https://antigravity.codes/blog/antigravity-mcp-tutorial)
- [Antigravity Workflows | Antigravity.codes](https://antigravity.codes/blog/workflows)
- [Hooks in Antigravity – Google AI Developers Forum](https://discuss.ai.google.dev/t/hooks-in-antigravity/120458)
- [OpenAI Launches Plugin Marketplace for Codex | Winbuzzer](https://winbuzzer.com/2026/03/31/openai-launches-plugin-marketplace-codex-enterprise-controls-xcxwbn/)
- [GitHub Copilot in Visual Studio Code, April releases](https://github.blog/changelog/2026-05-06-github-copilot-in-visual-studio-code-april-releases/)
