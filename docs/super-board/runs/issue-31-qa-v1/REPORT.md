# QA Report — Issue #31 "support Copilot CLI" — v1

- Lane: Tester (QA -> Review) | Branch: issue-31-support-copilot-cli | PR: #32 | Base: master
- Result: PASS — all 16 ACs green; no regressions attributable to this branch.
- Test env: fresh .venv (pytest 9.1.0); deps: pyyaml, click, tomli_w, xarray, numpy.

## Per-AC results (verify commands run exactly as written in the issue)

| AC | Verify | Result |
|----|--------|--------|
| AC1 | tools.build --list grep | PASS — copilot-cli AND copilot both present |
| AC2 | build + grep helpers | PASS — exit 0, build/copilot-cli/metplot/ created; copy_skills/copy_install_tooling/common_metplot_block referenced |
| AC3 | pytest test_mcp_config.py | PASS — top key mcpServers, servers absent |
| AC4 | pytest test_mcp_config.py | PASS — both servers type:local, command=entry_point, args:[], tools:["*"] |
| AC5 | pytest test_skills_copied.py | PASS (8) — 6 allowlisted skills each w/ SKILL.md |
| AC6 | pytest test_mcp_servers_bundled.py + inspect | PASS — re-rooted server.py paths + pyproject include=["src","src.*"] |
| AC7 | pytest test_all_targets_have_setup.py + test_setup_files.py | PASS (12, 1 pre-existing hermes skip) |
| AC8 | pytest test_manifest.py + read | PASS — build_cycle==7, exact ships_skills + ships_mcp_servers |
| AC9 | pytest node + grep | PASS — _BUILDS has copilot-cli; test_skill_refiner_shipped[copilot-cli] green |
| AC10 | pytest node + ls | PASS — copilot_cli dir w/ test_skills_copied, __init__, conftest; coverage guard green |
| AC11 | build copilot-cli --validate | PASS — exit 0, 24 passed, "validation passed" |
| AC12 | pytest -k copilot-cli (hyphenated) | PASS — 1 passed; underscore deselects all (as warned) |
| AC13 | grep + pytest tests/docs/test_installation_doc.py | PASS (7) — section has build/install/enable/verify steps |
| AC14 | awk-extract + grep | PASS — mcp-config.json x3, mcpServers x1, ~/.copilot x3 in CLI section |
| AC15a | pytest tests/targets/copilot_cli/ | PASS — 24 passed in isolation |
| AC15b | pytest tests/targets/copilot/ | PASS — 35 passed; test_servers_key still asserts servers present / mcpServers absent |
| AC16 | grep + diff review | PASS — survey.md:340 stale claim substantively corrected |

## Regression sweep
- pytest tests/targets -> 337 passed, 2 skipped, 0 failed (1 deselected).
- 2 skips = pre-existing hermes stubs (unrelated).
- 1 deselected: claude_code/test_mcp_smoke.py::test_bundled_server_imports[plot_renderer] fails only on missing heavy dep (matplotlib/cartopy) in QA venv; it imports the real claude_code MCP server, which this branch does NOT touch.
- NOT-A-REGRESSION PROOF: git diff --stat master...HEAD -- tests/targets/claude_code/ src/ targets/_common/ is EMPTY. Branch is purely additive.
- pytest tests/docs -> 7 passed.

## gh quota on exit
graphql=4746/5000 rest(core)=4998/5000

## Verdict: PASS -> move QA -> Review.
