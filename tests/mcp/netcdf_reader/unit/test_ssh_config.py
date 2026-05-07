# tests/mcp/netcdf_reader/unit/test_ssh_config.py
from src.mcp.netcdf_reader.paths.ssh import (
    SSHConfig, parse_ssh_config_for_host,
)


def test_ssh_config_dataclass_defaults():
    cfg = SSHConfig(host="h")
    assert cfg.host == "h"
    assert cfg.port == 22
    assert cfg.user is None
    assert cfg.identity_file is None
    assert cfg.jump is None


def test_parse_ssh_config_simple_alias(tmp_path):
    cfile = tmp_path / "ssh_config"
    cfile.write_text(
        "Host hpc\n"
        "  HostName hpc.example.org\n"
        "  User youngsung\n"
        "  IdentityFile ~/.ssh/id_rsa\n"
        "  Port 2222\n"
    )
    cfg = parse_ssh_config_for_host("hpc", config_path=str(cfile))
    assert cfg.host == "hpc.example.org"
    assert cfg.user == "youngsung"
    assert cfg.port == 2222
    assert cfg.identity_file == "~/.ssh/id_rsa"


def test_parse_ssh_config_no_match_returns_passthrough(tmp_path):
    cfile = tmp_path / "ssh_config"
    cfile.write_text("Host other\n  HostName other.example.org\n")
    cfg = parse_ssh_config_for_host("missing", config_path=str(cfile))
    assert cfg.host == "missing"
    assert cfg.user is None


def test_parse_ssh_config_with_proxyjump(tmp_path):
    cfile = tmp_path / "ssh_config"
    cfile.write_text(
        "Host inner\n"
        "  HostName internal.hpc.org\n"
        "  User u\n"
        "  ProxyJump bastion\n"
        "Host bastion\n"
        "  HostName bastion.example.org\n"
        "  User u\n"
    )
    cfg = parse_ssh_config_for_host("inner", config_path=str(cfile))
    assert cfg.host == "internal.hpc.org"
    assert cfg.jump is not None
    assert cfg.jump.host == "bastion.example.org"
