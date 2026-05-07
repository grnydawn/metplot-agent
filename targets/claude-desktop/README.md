# Claude Desktop target

Build with:

```
python -m tools.build claude-desktop
```

Output: `build/claude-desktop/ncplot-agent-claude-desktop/`.

Claude Desktop has no native skill loader, so this builder packages skill
content as a project-attachable `project_instructions.md` and emits MCP
server config the user merges into their Desktop config.

See the generated README inside the build artifact for install steps.
