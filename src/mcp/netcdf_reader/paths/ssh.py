# src/mcp/netcdf_reader/paths/ssh.py
"""⤴ format-agnostic — eligible for _core/ lift.

SSH transport. paramiko opens an SFTP client; xarray reads the file
through it via the h5netcdf engine. Connection pool is session-scoped.
Credentials live only in process memory.

This module is built up across Tasks 32–39. Read the spec §7.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import paramiko


@dataclass
class SSHConfig:
    host: str
    port: int = 22
    user: str | None = None
    identity_file: str | None = None
    passphrase: str | None = None  # for encrypted keys
    password: str | None = None
    jump: "SSHConfig | None" = None
    session_id: str | None = None


def parse_ssh_config_for_host(
    alias: str, *, config_path: str | None = None
) -> SSHConfig:
    """Use paramiko's SSHConfig parser to resolve a host alias from the
    user's ~/.ssh/config (or the given config_path). Returns a passthrough
    SSHConfig if no alias matches."""
    if config_path is None:
        config_path = str(Path.home() / ".ssh" / "config")
    if not Path(config_path).exists():
        return SSHConfig(host=alias)

    sc = paramiko.SSHConfig()
    with open(config_path) as fh:
        sc.parse(fh)

    look = sc.lookup(alias)
    host = look.get("hostname", alias)
    port = int(look.get("port", 22))
    user = look.get("user")
    identity = (look.get("identityfile") or [None])[0]
    # paramiko expands ~ to $HOME; keep the un-expanded form for portability
    if identity:
        home = str(Path.home())
        if identity.startswith(home + os.sep):
            identity = "~" + identity[len(home):]

    jump = None
    pj = look.get("proxyjump")
    if pj:
        # ProxyJump may be "bastion" or "user@bastion:port"
        # Recurse to resolve the jump host's own config
        if "@" in pj:
            j_user, j_host = pj.split("@", 1)
        else:
            j_user, j_host = None, pj
        if ":" in j_host:
            j_host, j_port = j_host.split(":", 1)
            j_port = int(j_port)
        else:
            j_port = 22
        jump_resolved = parse_ssh_config_for_host(j_host, config_path=config_path)
        if j_user:
            jump_resolved.user = j_user
        if j_port != 22:
            jump_resolved.port = j_port
        jump = jump_resolved

    return SSHConfig(
        host=host, port=port, user=user, identity_file=identity, jump=jump,
    )
