
from tools.install_deps import parse_args, Args


def test_defaults():
    a = parse_args([])
    assert isinstance(a, Args)
    assert a.no_cartopy is False
    assert a.no_scipy is False
    assert a.quiet is False
    assert a.dry_run is False
    assert a.force is False
    assert a.mcp_servers_dir is None


def test_no_cartopy():
    a = parse_args(["--no-cartopy"])
    assert a.no_cartopy is True


def test_quiet():
    a = parse_args(["--quiet"])
    assert a.quiet is True


def test_dry_run():
    a = parse_args(["--dry-run"])
    assert a.dry_run is True


def test_force():
    a = parse_args(["--force"])
    assert a.force is True


def test_mcp_servers_dir():
    a = parse_args(["--mcp-servers-dir", "/tmp/mcp"])
    assert str(a.mcp_servers_dir) == "/tmp/mcp"


def test_combined():
    a = parse_args(["--no-cartopy", "--no-scipy", "--quiet", "--force"])
    assert a.no_cartopy and a.no_scipy and a.quiet and a.force
