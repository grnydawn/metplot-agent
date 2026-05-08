# tests/targets/_common/test_mcp_bundling_helper.py
from pathlib import Path


from targets._common.mcp_bundling import MCP_SERVERS, bundle_mcp_servers


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"


def test_mcp_servers_descriptors():
    names = {s["external_name"] for s in MCP_SERVERS}
    assert names == {"netcdf-reader", "plot-renderer"}
    for s in MCP_SERVERS:
        assert "package_dir" in s
        assert "external_name" in s
        assert "entry_point" in s


def test_bundle_creates_re_rooted_source(tmp_path):
    bundle_mcp_servers(SRC_ROOT, tmp_path)
    for s in MCP_SERVERS:
        bundled = tmp_path / s["package_dir"] / "src" / "mcp" / s["package_dir"]
        assert bundled.is_dir(), f"missing re-rooted package: {bundled}"
        assert (bundled / "__init__.py").is_file()
        assert (bundled / "server.py").is_file()


def test_bundle_patches_pyproject(tmp_path):
    bundle_mcp_servers(SRC_ROOT, tmp_path)
    for s in MCP_SERVERS:
        pp = tmp_path / s["package_dir"] / "pyproject.toml"
        assert pp.is_file()
        text = pp.read_text()
        assert "[tool.setuptools.packages.find]" in text
        assert 'where = ["src"]' in text


def test_bundle_returns_descriptor_list(tmp_path):
    result = bundle_mcp_servers(SRC_ROOT, tmp_path)
    assert isinstance(result, list)
    assert {r["external_name"] for r in result} == {
        "netcdf-reader", "plot-renderer"}
