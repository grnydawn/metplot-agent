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


@dataclass
class AuthAttempt:
    method: str
    result: str  # "success" | "no_keys" | "rejected" | "skipped"
    detail: str = ""


class SSHAuthNeeded(Exception):
    """Raised when silent auth chain exhausts all options. The agent
    layer converts this into an `ssh_auth_needed` envelope."""
    def __init__(self, cfg: SSHConfig, attempts: list[AuthAttempt],
                 may_need_jump_host: bool = False):
        self.cfg = cfg
        self.attempts = attempts
        self.may_need_jump_host = may_need_jump_host
        super().__init__(f"SSH auth needed for {cfg.user}@{cfg.host}")


def _default_identity_files() -> list[str]:
    home = Path.home()
    return [str(home / ".ssh" / n)
            for n in ("id_ed25519", "id_rsa", "id_ecdsa")
            if (home / ".ssh" / n).exists()]


def silent_auth_chain(
    cfg: SSHConfig,
) -> tuple[paramiko.SSHClient, list[AuthAttempt]]:
    """Try each silent auth method in order. Return the connected
    client + the trace of attempts. Raise SSHAuthNeeded on total failure.
    """
    attempts: list[AuthAttempt] = []
    user = cfg.user or os.environ.get("USER") or "root"

    # 1. ssh-agent (only if SSH_AUTH_SOCK is set)
    if os.environ.get("SSH_AUTH_SOCK"):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=cfg.host, port=cfg.port, username=user,
                allow_agent=True, look_for_keys=False,
                timeout=10,
            )
            attempts.append(AuthAttempt("ssh_agent", "success"))
            return client, attempts
        except paramiko.AuthenticationException:
            attempts.append(AuthAttempt("ssh_agent", "rejected"))
        except (OSError, paramiko.SSHException) as e:
            attempts.append(AuthAttempt("ssh_agent", "rejected", str(e)))
    else:
        attempts.append(AuthAttempt("ssh_agent", "skipped",
                                    "SSH_AUTH_SOCK not set"))

    # 2. Default identity files
    if cfg.identity_file:
        candidates = [cfg.identity_file]
    else:
        candidates = _default_identity_files()
    if not candidates:
        attempts.append(AuthAttempt("default_identity_files", "no_keys"))
    for ident in candidates:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=cfg.host, port=cfg.port, username=user,
                key_filename=ident, allow_agent=False, look_for_keys=False,
                timeout=10,
            )
            attempts.append(AuthAttempt("default_identity_files", "success",
                                        ident))
            return client, attempts
        except paramiko.AuthenticationException:
            attempts.append(AuthAttempt("default_identity_files", "rejected",
                                        ident))
        except paramiko.PasswordRequiredException:
            attempts.append(AuthAttempt("default_identity_files",
                                        "needs_passphrase", ident))
        except (OSError, paramiko.SSHException) as e:
            attempts.append(AuthAttempt("default_identity_files",
                                        "rejected", f"{ident}: {e}"))

    raise SSHAuthNeeded(cfg=cfg, attempts=attempts)


class SSHAuthFailed(Exception):
    pass


def connect_explicit(cfg: SSHConfig) -> paramiko.SSHClient:
    """Connect using credentials present in `cfg`. Raises SSHAuthFailed
    on rejection. Never logs sensitive fields."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    user = cfg.user or os.environ.get("USER") or "root"
    try:
        kwargs: dict[str, Any] = dict(
            hostname=cfg.host, port=cfg.port, username=user,
            allow_agent=False, look_for_keys=False, timeout=10,
        )
        if cfg.password is not None:
            kwargs["password"] = cfg.password
        if cfg.identity_file is not None:
            kwargs["key_filename"] = cfg.identity_file
            if cfg.passphrase is not None:
                kwargs["passphrase"] = cfg.passphrase
        client.connect(**kwargs)
        return client
    except paramiko.AuthenticationException as e:
        raise SSHAuthFailed(f"auth rejected for {user}@{cfg.host}") from None
    except (OSError, paramiko.SSHException) as e:
        # Don't include cfg in the exception message — could leak
        raise SSHAuthFailed(f"connection error: {type(e).__name__}") from None


class ConnectionPool:
    """Session-scoped pool keyed by (user, host, port). Credentials
    live only in the in-memory cfg objects; cleared on close_all()."""
    def __init__(self) -> None:
        self._pool: dict[tuple[str, str, int], tuple[paramiko.SSHClient, SSHConfig]] = {}

    def _key(self, cfg: SSHConfig) -> tuple[str, str, int]:
        return (cfg.user or "", cfg.host, cfg.port)

    def get_or_open(self, cfg: SSHConfig) -> paramiko.SSHClient:
        k = self._key(cfg)
        if k in self._pool:
            return self._pool[k][0]
        client = connect_explicit(cfg)
        self._pool[k] = (client, cfg)
        return client

    def close_all(self) -> None:
        for client, cfg in list(self._pool.values()):
            try:
                client.close()
            except Exception:
                pass
            # Zero credentials
            cfg.password = None
            cfg.passphrase = None
        self._pool.clear()
