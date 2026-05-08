# Plugin install lifecycle hooks — survey (May 2026)

Focused follow-up to `2026-05-08-multi-host-survey.md`. Question: do
the 7 cycle-7 target hosts support a post-install lifecycle hook that
can run a shell command automatically the first time the plugin loads
or when the user installs it? Conducted at the start of cycle 5 to
decide whether ncplot-agent's dependency installer can be auto-fired
or has to be a manual `setup.sh`.

## At-a-glance

| Host | Install hook | Format | Runs shell? | Failure mode | Usability |
|------|--------------|--------|-------------|--------------|-----------|
| Claude Code | None (`onInstall` unimplemented); `SessionStart` + `${CLAUDE_PLUGIN_DATA}` idempotency guard is the documented workaround | `hooks/hooks.json` `"SessionStart"` event with `"type":"command"` | Yes — full shell command | Hook failure → guard sentinel removed → retries next session; plugin still loads | Stable; canonical pattern in docs |
| Codex CLI | None; `SessionStart` exists but **plugin-local hooks.json is broken** (issue #16430, open) | Manifest `hooks` field; only `~/.codex/hooks.json` actually fires | Yes (in spec) | Plugin loads silently; bundled hooks ignored | Preview-class; broken at runtime |
| Gemini CLI | None — no install lifecycle field in `gemini-extension.json` | `hooks/hooks.json` inside extension; events are session/tool/model-scoped only | Yes — `"type":"command"` | Not documented; extension loads regardless | Stable; no install hook exists or is planned |
| Cursor | None — `onInstall` absent; `sessionStart` fires every session | `.cursor-plugin/plugin.json` `hooks` field; `"sessionStart"` event | Yes — `"command":"./scripts/foo.sh"` | Plugin loads regardless; errors logged in Cursor's plugin error tab | Stable; no install-specific event |
| GitHub Copilot (agent plugin) | None — `onInstall` absent; `SessionStart` is earliest event | `plugin.json` `hooks` or `hooks.json`; `"SessionStart"` with `"type":"command"` | Yes — shell commands explicitly documented | Not documented | Preview (agent-plugin format) |
| Antigravity | None — no formal plugin manifest system, no hook infrastructure | n/a — community workarounds only (GEMINI.md rules, manual session activation, ag_plugin_*.py scanning) | n/a | n/a | No formal plugin system |
| Claude Desktop (.mcpb) | None — `manifest.json` has no lifecycle field of any kind | Static `manifest.json` for server registration only | No — install writes config entries only; server binary runs at connection time | Install succeeds; bad server config surfaces as connection error at first use | Stable; by design does not execute code at install |

## Per-host details

### Claude Code

No `onInstall` field exists in `.claude-plugin/plugin.json`. A GitHub
feature request (#11240, opened Nov 2025) asked for `PreInstall`/
`PostInstall`/`PreUninstall`/`PostUninstall` hooks and was closed as a
duplicate, meaning the canonical request is tracked elsewhere but is
still unimplemented as of May 2026.

The officially documented substitute is `SessionStart` combined with
`${CLAUDE_PLUGIN_DATA}`. The docs provide a verbatim pattern: `diff`
the bundled `package.json` against a copy in the persistent data
directory; if they differ (first run or after an update), run install
into `${CLAUDE_PLUGIN_DATA}`. This fires every session but is
effectively a once-per-change guard. The `Setup` event fires only when
Claude Code is launched with `--init-only` or `--init`/`--maintenance`
in `-p` mode — useful for CI but not for normal user installs.

**Bottom line:** No true `onInstall`. The `SessionStart` +
`${CLAUDE_PLUGIN_DATA}` diff-guard is the canonical workaround and is
stable.

### Codex CLI / Desktop

The manifest `hooks` field accepts a path to `hooks/hooks.json` or an
inline object. Supported events are `SessionStart`, `PreToolUse`,
`PermissionRequest`, `PostToolUse`, `UserPromptSubmit`, and `Stop` —
no install-time event.

GitHub issue #16430 (open as of May 2026) documents that
**plugin-local hooks do not actually fire at runtime**. The manifest
parser does not recognize the `hooks` field, and hook discovery only
scans global config directories (`~/.codex/hooks.json`). Hooks placed
inside a plugin bundle are silently ignored.

**Bottom line:** `onInstall` absent; `SessionStart` exists in spec but
is broken for plugin-bundled hooks. Do not rely on auto-fire.

### Gemini CLI

The `gemini-extension.json` manifest schema documents `name`, `version`,
`description`, `mcpServers`, `contextFileName`, `excludeTools`,
`settings`, `themes`, and `plan` — no install lifecycle field.
Hook definitions live in `hooks/hooks.json` inside the extension; the
hook system supports `SessionStart`, `SessionEnd`, `BeforeAgent`,
`AfterAgent`, `BeforeModel`, `AfterModel`, `BeforeTool`, `AfterTool`,
`BeforeToolSelection`, `PreCompress`, and `Notification`. No
`onInstall` or analogous event.

A `SessionStart` hook with a guard script could replicate first-run
behaviour, but Gemini's docs do not provide an explicit pattern for
this.

**Bottom line:** No install hook. `SessionStart` works for a manual
once-per-session guard if the plugin author implements one.

### Cursor

`.cursor-plugin/plugin.json` supports `name`, `description`, `version`,
`author`, `homepage`, `repository`, `license`, `keywords`, `rules`,
`agents`, `skills`, `commands`, `hooks`, and `mcpServers`. No
`onInstall` or `postInstall` field.

The `sessionStart` hook fires at every session start — the docs do
not distinguish first-install from subsequent sessions. Hooks execute
shell commands. Cursor's hook error tab surfaces failures; the plugin
continues to load regardless.

**Bottom line:** No install-specific hook. `sessionStart` fires every
session; implement your own idempotency guard if you need once-only
behaviour.

### GitHub Copilot (agent plugin)

The agent-plugin `plugin.json` (distinct from a regular VS Code
extension's `activate()` function) supports `name`, `description`,
`version`, `author`, `skills`, `agents`, `hooks`, and `mcpServers`. No
`onInstall`, `postInstall`, or `setup` field.

VS Code docs explicitly state: "Plugin hooks operate only at runtime
lifecycle points, not during initial installation." Supported hook
events mirror Claude Code's. Hooks use `"type":"command"` with
`${CLAUDE_PLUGIN_ROOT}` substitution. Failure mode is undocumented;
plugin continues to load.

The agent-plugin format remains in Preview; enterprise-managed plugins
entered public preview on 2026-05-06.

**Bottom line:** No install hook. `SessionStart` with a guard is the
closest option. Format is preview-quality and subject to change.

### Antigravity

Antigravity has no formal plugin manifest system comparable to the
other hosts. There is no `.antigravity-plugin/` directory convention,
no `onInstall`, and no `SessionStart`-equivalent hook infrastructure.
Community tooling relies on `GEMINI.md` rule files, manual per-session
activation, or Python sidecar files matching `ag_plugin_*.py` —
all unofficial, no shell lifecycle hooks.

**Bottom line:** No install hook, no hook system at all in the formal
sense.

### Claude Desktop (.mcpb)

The `.mcpb` bundle is a ZIP archive. Its `manifest.json` spec covers
metadata, server config, display fields, `user_config` for prompted
values, and compatibility constraints. No `onInstall`, `postInstall`,
`setup`, or any shell-executing lifecycle field anywhere in the spec.
Installation writes the server's connection config into
`claude_desktop_config.json`; no code is executed.

**Bottom line:** By design, `.mcpb` does not execute arbitrary code at
install time. Zero hook support.

## Recommendation

### Can we rely on native install hooks for a critical-path automatic dependency install on first load?

**No.** Not on any host. Zero hosts expose a true `onInstall` event
that runs once, at install time, before first use. The closest
functional equivalent is `SessionStart` with an idempotency guard —
available on Claude Code (stable, officially documented with
`${CLAUDE_PLUGIN_DATA}`), Gemini CLI (stable, no official pattern),
Cursor (stable, no official pattern), and Copilot (preview). Codex
CLI's plugin-local hooks are outright broken.

### Can we rely on native lifecycle hooks for an optional one-time setup shortcut?

**Yes, partially — only on Claude Code reliably.** Claude Code's
`SessionStart` + `${CLAUDE_PLUGIN_DATA}` diff-guard is the only setup
pattern that is (a) stable, (b) officially documented with a working
example, and (c) uses a dedicated persistent directory. The same
pattern can be manually implemented on Cursor and Gemini CLI with less
official support. Copilot is preview-quality. Antigravity and Claude
Desktop have no mechanism at all.

### Unavoidable manual fallback

`setup.sh` (or equivalent) must ship regardless. It is the only
reliable path for:

- Claude Desktop (no hook mechanism)
- Antigravity (no hook mechanism)
- Codex CLI (hooks broken in plugin bundles)
- Any user who installs the plugin in a non-interactive or CI context
  where `SessionStart` hooks don't fire

The recommended split: **ship `setup.sh` as the canonical path; layer
`SessionStart` guards on Claude Code (and optionally Cursor/Gemini) as
a convenience that runs it automatically — but never make `setup.sh`
unnecessary for all hosts.**

## Sources

- [Claude Code Plugins reference](https://code.claude.com/docs/en/plugins-reference)
- [Claude Code feature request #11240 — Plugin Lifecycle Hooks](https://github.com/anthropics/claude-code/issues/11240)
- [Codex hooks documentation](https://developers.openai.com/codex/hooks)
- [Codex build plugins documentation](https://developers.openai.com/codex/plugins/build)
- [Codex bug #16430 — plugin-local hooks.json not executed](https://github.com/openai/codex/issues/16430)
- [Gemini CLI extension reference](https://geminicli.com/docs/extensions/reference/)
- [Gemini CLI hooks documentation](https://geminicli.com/docs/hooks/)
- [Cursor Plugins docs](https://cursor.com/docs/plugins)
- [Cursor Plugins reference / building](https://cursor.com/docs/plugins/building)
- [GitHub Copilot agent plugins in VS Code (Preview)](https://code.visualstudio.com/docs/copilot/customization/agent-plugins)
- [Enterprise-managed plugins in GitHub Copilot CLI — public preview](https://github.blog/changelog/2026-05-06-enterprise-managed-plugins-in-github-copilot-cli-are-now-in-public-preview/)
- [MCPB GitHub repository](https://github.com/modelcontextprotocol/mcpb)
- [Building Desktop Extensions with MCPB — Claude Help Center](https://support.claude.com/en/articles/12922929-building-desktop-extensions-with-mcpb)
- [Antigravity community hooks repo](https://github.com/fpozoc/antigravity-hooks)
