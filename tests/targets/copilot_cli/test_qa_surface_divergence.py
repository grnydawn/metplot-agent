"""QA regression guard (issue #31) — the two Copilot targets must never
converge on the same MCP surface.

The whole reason `copilot-cli` exists as a separate target is that the
standalone CLI uses `~/.copilot/mcp-config.json` keyed on `mcpServers`
with `type: "local"` entries, while the VS Code plugin (`targets/copilot/`)
uses `.vscode/mcp.json` keyed on `servers`. A future cross-target
copy-paste could silently make them identical; this test fails loudly if
that ever happens. It builds BOTH targets and asserts they diverge.

Owned by: QA (super-board Tester lane).
"""
import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"


def _load_build(target_dir_name: str):
    build_py = REPO_ROOT / "targets" / target_dir_name / "build.py"
    spec = importlib.util.spec_from_file_location(
        f"targets.{target_dir_name.replace('-', '_')}.build", build_py)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def cli_config(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("qa-copilot-cli")
    _load_build("copilot-cli").build(SRC_ROOT, out)
    return json.loads((out / "metplot" / "mcp-config.json").read_text())


@pytest.fixture(scope="module")
def vscode_config(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("qa-copilot-vscode")
    _load_build("copilot").build(SRC_ROOT, out)
    return json.loads(
        (out / "metplot" / ".vscode" / "mcp.json").read_text())


def test_cli_and_vscode_use_different_top_level_keys(cli_config, vscode_config):
    """The defining contrast: CLI -> mcpServers, VS Code -> servers."""
    assert "mcpServers" in cli_config and "servers" not in cli_config, (
        "copilot-cli must key on mcpServers (not servers)")
    assert "servers" in vscode_config and "mcpServers" not in vscode_config, (
        "copilot (VS Code) must key on servers (not mcpServers)")
    assert set(cli_config.keys()) != set(vscode_config.keys()), (
        "the two Copilot targets converged on the same MCP surface — "
        "this is the cross-target copy-paste regression issue #31 guards against")


def test_cli_servers_declare_local_type(cli_config):
    """Every CLI server is a local stdio entry — the VS Code surface omits
    `type: local` (its servers are declared differently), so this is unique
    to the CLI config."""
    servers = cli_config["mcpServers"]
    assert servers, "expected at least one bundled server in the CLI config"
    for name, spec in servers.items():
        assert spec.get("type") == "local", (
            f"{name} must be a local stdio server in the standalone CLI config")
