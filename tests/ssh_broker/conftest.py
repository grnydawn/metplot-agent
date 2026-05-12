"""In-process paramiko sshd for integration testing.

Spins a paramiko Transport on 127.0.0.1:<random>. Accepts
password auth (testuser/testpass). Implements:

  - SFTP subsystem (list_folder, stat, open for read) jailed to a
    temp root.
  - Exec channels for a small command emulation: ncdump -h, ncks
    -m, ls. Anything else → exit 127 "command not found".

The exec emulation is just enough for the broker's dump_header /
dump_metadata / exec methods to be exercised end-to-end. We don't
spawn real subprocesses — we generate the stub output in-process
based on the command string parsing.

Reference: paramiko/demos/demo_server.py.
"""
from __future__ import annotations

import os
import shlex
import socket
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import paramiko
import pytest


# Use 1024-bit key for faster generation in tests (still secure enough for local loopback)
_HOST_KEY = paramiko.RSAKey.generate(1024)


# ── SFTP handler ───────────────────────────────────────────────

class _RootedSFTPHandler(paramiko.SFTPServerInterface):
    """Per-class _ROOT — bind one subclass per test via with_root()."""

    _ROOT: str = ""

    @classmethod
    def with_root(cls, root: str):
        return type(f"_SFTPHandler_bound", (cls,), {"_ROOT": root})

    def _real(self, path: str) -> str:
        # If the client sends the actual real path (e.g. sftp.listdir(root)),
        # pass it through directly when it's already under _ROOT.
        p = Path(path)
        root = Path(self._ROOT)
        if p.is_absolute():
            try:
                p.relative_to(root)
                return str(p)  # already a real absolute path under root
            except ValueError:
                pass
            # Strip leading "/" and join under root (normal jail logic)
            return str(root / path.lstrip("/"))
        return str(root / path)

    def list_folder(self, path):
        real = self._real(path)
        try:
            entries = []
            for name in sorted(Path(real).iterdir()):
                a = paramiko.SFTPAttributes.from_stat(
                    name.stat(), filename=name.name)
                entries.append(a)
            return entries
        except FileNotFoundError:
            return paramiko.SFTP_NO_SUCH_FILE
        except OSError:
            return paramiko.SFTP_FAILURE

    def stat(self, path):
        real = self._real(path)
        try:
            return paramiko.SFTPAttributes.from_stat(Path(real).stat())
        except FileNotFoundError:
            return paramiko.SFTP_NO_SUCH_FILE

    lstat = stat

    def open(self, path, flags, attr):
        real = self._real(path)
        try:
            f = open(real, "rb")
        except FileNotFoundError:
            return paramiko.SFTP_NO_SUCH_FILE
        h = paramiko.SFTPHandle(flags)
        h.readfile = f
        return h


# ── Exec emulation ─────────────────────────────────────────────

def _resolve_path(path: str, root: str) -> Path:
    """Map a remote path to a real filesystem path under root.

    If path is already absolute and under root, use it directly.
    Otherwise strip the leading "/" and join under root (jail logic).
    """
    p = Path(path)
    root_p = Path(root)
    if p.is_absolute():
        try:
            p.relative_to(root_p)
            return p  # already under root — pass through
        except ValueError:
            pass
        return root_p / path.lstrip("/")
    return root_p / path


def _emulate_command(command: str, root: str) -> tuple[bytes, bytes, int]:
    """Return (stdout, stderr, exit_code) for a known command, else
    127 'command not found'."""
    try:
        argv = shlex.split(command)
    except ValueError:
        return b"", f"sh: parse error: {command}".encode(), 2
    if not argv:
        return b"", b"", 0

    tool = argv[0]

    if tool == "ncdump" and len(argv) >= 3 and argv[1] == "-h":
        path = argv[2]
        real = _resolve_path(path, root)
        if not real.exists():
            return (b"",
                     f"ncdump: cannot open {path}: No such file\n".encode(),
                     2)
        # Stub CDL: just the header sentinel + filename. Enough for
        # downstream tests to recognize.
        basename = real.stem
        cdl = (f"netcdf {basename} {{\n"
                f"  dimensions:\n"
                f"  variables:\n"
                f"}}\n")
        return cdl.encode("utf-8"), b"", 0

    if tool == "ncks":
        # Fixture has no ncks installed.
        return (b"",
                 b"bash: ncks: command not found\n",
                 127)

    if tool == "ls":
        target = argv[1] if len(argv) > 1 else "."
        real = _resolve_path(target, root) if target != "." else Path(root)
        try:
            names = sorted(p.name for p in real.iterdir())
        except FileNotFoundError:
            return b"", f"ls: {target}: No such file\n".encode(), 2
        return ("\n".join(names) + "\n").encode("utf-8"), b"", 0

    return (b"",
             f"bash: {tool}: command not found\n".encode(),
             127)


# ── ServerInterface ────────────────────────────────────────────

class _InMemoryServer(paramiko.ServerInterface):
    """Accepts password testuser/testpass; routes session channels
    to either the SFTP subsystem or an exec stub."""

    def __init__(self, root: str) -> None:
        self.root = root
        self.event = threading.Event()

    def check_auth_password(self, username, password):
        if username == "testuser" and password == "testpass":
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def check_channel_request(self, kind, chanid):
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def get_allowed_auths(self, username):
        return "password"

    def check_channel_exec_request(self, channel, command):
        # paramiko gives us the command as bytes; spawn a worker
        # that writes stdout/stderr/exit_code, then closes.
        cmd = command.decode("utf-8") if isinstance(command, bytes) \
            else command

        def _worker():
            stdout, stderr, exit_code = _emulate_command(cmd, self.root)
            if stdout:
                channel.sendall(stdout)
            if stderr:
                channel.sendall_stderr(stderr)
            channel.send_exit_status(exit_code)
            channel.close()

        threading.Thread(target=_worker, daemon=True).start()
        return True


# ── Per-connection server handler ──────────────────────────────

def _handle_connection(client_sock: socket.socket, root: str,
                        stop: threading.Event) -> None:
    """Handle a single SSH client connection.

    Runs in its own daemon thread. Sets up the paramiko Transport,
    starts the server, then loops calling t.accept() to handle
    channels until the transport disconnects or the stop event fires.
    """
    t = paramiko.Transport(client_sock)
    t.add_server_key(_HOST_KEY)
    t.set_subsystem_handler(
        "sftp", paramiko.SFTPServer,
        _RootedSFTPHandler.with_root(root),
    )
    server = _InMemoryServer(root)
    try:
        t.start_server(server=server)
    except paramiko.SSHException:
        return

    # Accept channels until the transport closes or stop fires.
    # Without this loop the client can authenticate but the transport
    # has nobody calling accept(), so it stalls.
    while not stop.is_set() and t.is_active():
        chan = t.accept(timeout=0.5)
        if chan is None:
            # Timed out — loop again to check t.is_active() / stop
            continue
        # SFTP subsystem channels are handled transparently by the
        # subsystem handler set above.  Exec channels are handled by
        # check_channel_exec_request via _worker threads.
        # We just need to keep the loop going so more channels can be
        # accepted on the same connection.

    t.close()


# ── Server thread ──────────────────────────────────────────────

def _run_server_thread(srv_sock: socket.socket, root: str,
                        stop: threading.Event) -> None:
    """Accept TCP connections and spawn a handler thread for each."""
    srv_sock.settimeout(0.2)
    while not stop.is_set():
        try:
            client_sock, _ = srv_sock.accept()
        except socket.timeout:
            continue
        except OSError:
            return

        # Each client connection gets its own daemon thread so the
        # server loop can continue accepting new connections.
        handler = threading.Thread(
            target=_handle_connection,
            args=(client_sock, root, stop),
            daemon=True,
        )
        handler.start()


# ── Fixture ────────────────────────────────────────────────────

@dataclass
class _InprocSSHDHandle:
    port: int
    root: str


@pytest.fixture
def inproc_sshd(tmp_path):
    """Yield (port, root) for an in-process sshd."""
    root = tmp_path / "remote-root"
    root.mkdir()
    (root / "alpha.nc").write_bytes(b"\x89HDF\r\n\x1a\n" + b"\x00" * 32)
    (root / "beta.nc").write_bytes(b"\x89HDF\r\n\x1a\n" + b"\x01" * 32)
    (root / "skip.txt").write_text("not a netcdf")

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    port = srv.getsockname()[1]
    srv.listen(8)

    stop = threading.Event()
    t = threading.Thread(target=_run_server_thread,
                          args=(srv, str(root), stop), daemon=True)
    t.start()
    try:
        yield _InprocSSHDHandle(port=port, root=str(root))
    finally:
        stop.set()
        try:
            srv.close()
        except Exception:
            pass
        t.join(timeout=3)
