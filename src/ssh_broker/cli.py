"""metplot-ssh-broker CLI.

User invokes this in their own terminal BEFORE launching Claude Code:

    metplot-ssh-broker home.ccs.ornl.gov

The CLI prompts via getpass (passcode visible only to the user's
terminal), passes it to paramiko.connect(), drops it from memory,
then runs the JSON-RPC server. Foreground process — the user can
background it with `&` or run it in a separate tmux pane.

Channel model: the broker holds ONE paramiko SSH transport, and the
SessionHolder mutex arbitrates a single session-channel slot between
SFTP (default) and short-lived exec. OLCF MaxSessions=1 compatible.
"""
from __future__ import annotations

import argparse
import getpass
import os
import signal
import sys
import threading
from pathlib import Path
from typing import Any

import paramiko

from src.ssh_broker.server import serve_forever
from src.ssh_broker.session_holder import SessionHolder


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="metplot-ssh-broker",
        description=(
            "Persistent SSH/SFTP+exec broker. Authenticates once in "
            "your terminal, exposes a local UNIX socket the metplot "
            "MCP uses without ever seeing your credential."
        ),
    )
    p.add_argument("host", help="remote hostname (e.g. home.ccs.ornl.gov)")
    p.add_argument("--user", default=None,
                    help="remote username (default: $USER)")
    p.add_argument("--port", type=int, default=22, help="SSH port (default 22)")
    p.add_argument("--socket-dir", default=None,
                    help="directory for the UNIX socket "
                          "(default: $XDG_RUNTIME_DIR/metplot-ssh or "
                          "/tmp/metplot-ssh)")
    p.add_argument("--idle-timeout", type=float, default=7200.0,
                    help="exit after N seconds with no requests (default 7200)")
    p.add_argument("--keepalive", type=int, default=30,
                    help="paramiko keepalive interval in seconds (default 30)")
    p.add_argument("--allow-exec", default=None,
                    help="comma-separated extra tool names allowed via "
                          "exec() beyond the built-in read-only set "
                          "(e.g. 'ncks,find')")
    return p


def default_socket_path(host: str, socket_dir: str | None) -> str:
    """Where the broker socket lives. Per host."""
    if socket_dir is not None:
        base = socket_dir
    else:
        runtime = os.environ.get("XDG_RUNTIME_DIR")
        base = os.path.join(runtime, "metplot-ssh") if runtime \
            else "/tmp/metplot-ssh"
    return str(Path(base) / f"{host}.sock")


def _split_user_host(
    host_arg: str, explicit_user: str | None
) -> tuple[str, str | None]:
    """Parse `user@host` syntax. --user wins on conflict. Split on first @.

    Returns (host, user). user may be None if no prefix and no explicit_user.
    Exits with code 2 on empty username or empty host.
    """
    if "@" not in host_arg:
        return host_arg, explicit_user
    prefix, _, rest = host_arg.partition("@")
    if not prefix:
        print(
            f"ERROR: invalid host argument '{host_arg}': "
            f"empty username before '@'",
            file=sys.stderr,
        )
        raise SystemExit(2)
    if not rest:
        print(
            f"ERROR: invalid host argument '{host_arg}': "
            f"empty host after '@'",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return rest, (explicit_user if explicit_user else prefix)


def resolve_user_and_host(ns: argparse.Namespace) -> tuple[str, str]:
    """Final (host, user) after user@host split + $USER fallback.

    The returned `user` is always a non-empty string (defaults to
    $USER, then 'root' if $USER is unset).
    """
    host, user_from_prefix = _split_user_host(ns.host, ns.user)
    user = user_from_prefix or os.environ.get("USER") or "root"
    return host, user


def _authenticate(host: str, user: str, port: int,
                   keepalive: int) -> SessionHolder:
    """Read passcode interactively; connect; drop credential immediately."""
    passcode = getpass.getpass(
        f"{user}@{host}:{port} passcode (in-memory only, will be dropped): "
    )
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host, port=port, username=user,
            password=passcode,
            allow_agent=False, look_for_keys=False, timeout=15,
        )
    finally:
        # Best-effort scrub. Python strings are immutable so we can't
        # zero the buffer; relying on the local binding falling out of
        # scope at function return.
        passcode = ""
        del passcode
    return SessionHolder(client=client, host=host, user=user,
                          keepalive_interval=keepalive)


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    user = ns.user or os.environ.get("USER") or "root"
    sock_path = default_socket_path(ns.host, ns.socket_dir)

    if Path(sock_path).exists():
        print(f"ERROR: {sock_path} already exists. Another broker may "
              f"be running for this host.", file=sys.stderr)
        return 3

    extra_allowed: set[str] = set()
    if ns.allow_exec:
        extra_allowed = {s.strip() for s in ns.allow_exec.split(",")
                          if s.strip()}

    print(f"Connecting to {user}@{ns.host}:{ns.port}...", file=sys.stderr)
    try:
        holder = _authenticate(ns.host, user, ns.port, ns.keepalive)
    except paramiko.AuthenticationException:
        print("ERROR: authentication failed.", file=sys.stderr)
        return 4
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 5

    print(f"Connected. Socket: {sock_path}", file=sys.stderr)
    if extra_allowed:
        print(f"Extra exec tools allowed: {sorted(extra_allowed)}",
              file=sys.stderr)
    print("Leave this process running. Press Ctrl-C to exit.",
          file=sys.stderr)

    stop = threading.Event()

    def _on_signal(signum: int, _frame: Any) -> None:
        print(f"Received signal {signum}, shutting down.", file=sys.stderr)
        stop.set()

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    try:
        serve_forever(holder=holder, socket_path=sock_path,
                       stop_event=stop, idle_timeout=ns.idle_timeout,
                       extra_allowed=extra_allowed)
    finally:
        holder.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
