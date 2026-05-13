"""⤴ format-agnostic — eligible for _core/ lift.

Path scheme detection. Returns a structured ClassifiedPath that the
adapter uses to decide how to open. Format adapters declare which
schemes they support via FormatAdapter.supported_schemes.
"""
from __future__ import annotations

import glob as _glob
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse


class PathKind:
    LOCAL_SINGLE = "local_single"
    LOCAL_MULTI = "local_multi"
    REMOTE_URL = "remote_url"
    SSH_REMOTE = "ssh_remote"
    SSH_MULTI = "ssh_multi"  # cycle 14 — ssh:// glob expanded via broker


class ClassifyError(ValueError):
    pass


@dataclass
class ClassifiedPath:
    kind: str
    scheme: str
    paths: list[str] = field(default_factory=list)
    user: str | None = None
    host: str | None = None
    port: int | None = None
    remote_path: str | None = None
    raw: str = ""


_SSH_RE = re.compile(
    r"^ssh://(?:(?P<user>[^@]+)@)?(?P<host>[^:/]+)(?::(?P<port>\d+))?(?P<path>/.*)$"
)


def _has_glob(s: str) -> bool:
    return any(c in s for c in ["*", "?", "["])


def classify(raw: str) -> ClassifiedPath:
    if raw.startswith("ssh://"):
        m = _SSH_RE.match(raw)
        if not m:
            raise ClassifyError(f"malformed ssh URL: {raw!r}")
        port = int(m.group("port")) if m.group("port") else None
        host = m.group("host")
        remote_path = m.group("path")
        user = m.group("user")
        # Cycle 14: glob expansion via broker.
        if _has_glob(remote_path):
            from src.mcp.netcdf_reader.paths.ssh import (
                open_ssh_with_broker_fallback,
            )
            broker = open_ssh_with_broker_fallback(host)
            if broker is None:
                raise ClassifyError(
                    f"broker_required: Remote glob expansion for "
                    f"{raw!r} requires a running metplot-ssh broker. "
                    f"Run `metplot-ssh-broker {host}` in your terminal "
                    f"first.")
            matches = broker.glob_remote(remote_path)
            if not matches:
                raise ClassifyError(
                    f"no remote files matched glob: {raw!r}")
            user_prefix = f"{user}@" if user else ""
            port_suffix = f":{port}" if port else ""
            ssh_paths = [
                f"ssh://{user_prefix}{host}{port_suffix}{p}"
                for p in matches
            ]
            return ClassifiedPath(
                kind=PathKind.SSH_MULTI, scheme="ssh",
                user=user, host=host, port=port,
                paths=ssh_paths, raw=raw,
            )
        return ClassifiedPath(
            kind=PathKind.SSH_REMOTE,
            scheme="ssh",
            user=user,
            host=host,
            port=port,
            remote_path=remote_path,
            raw=raw,
        )

    parsed = urlparse(raw)
    scheme = parsed.scheme.lower()

    if scheme in ("http", "https", "s3", "gs", "abfs"):
        return ClassifiedPath(kind=PathKind.REMOTE_URL, scheme=scheme,
                              paths=[raw], raw=raw)

    if scheme and scheme != "file":
        raise ClassifyError(f"unsupported scheme: {scheme!r} in {raw!r}")

    # Local
    plain = parsed.path if scheme == "file" else raw
    if _has_glob(plain):
        matches = sorted(_glob.glob(plain))
        if not matches:
            raise ClassifyError(f"no files matched glob: {plain!r}")
        return ClassifiedPath(
            kind=PathKind.LOCAL_MULTI, scheme="file",
            paths=[str(Path(m).resolve()) for m in matches], raw=raw,
        )

    p = Path(plain)
    if not p.exists():
        raise ClassifyError(f"path not found: {plain!r}")

    if p.is_dir():
        files = sorted(p.glob("*.nc"))
        if not files:
            raise ClassifyError(f"directory has no .nc files: {plain!r}")
        return ClassifiedPath(
            kind=PathKind.LOCAL_MULTI, scheme="file",
            paths=[str(f.resolve()) for f in files], raw=raw,
        )

    return ClassifiedPath(
        kind=PathKind.LOCAL_SINGLE, scheme="file",
        paths=[str(p.resolve())], raw=raw,
    )
