"""SessionHolder — single-session-channel state machine.

Owns the paramiko SSHClient + transport. Arbitrates the one session
channel between SFTP (default-open) and short-lived exec. State
machine:

    [ SFTP open ]  ─ exec_command ─▶  close SFTP
                                       open exec channel
                                       run, collect output
                                       close exec channel
                                       leave SFTP = None
    [ SFTP None ]  ─ with_sftp ────▶  reopen SFTP
                                       run fn(sftp)

A threading.Lock serializes every public method. Concurrent
JSON-RPC clients can't race; the broker can only do one channel op
at a time anyway (OLCF MaxSessions=1).

Construction takes an already-connected paramiko.SSHClient — the
CLI handled auth and dropped the credential before building this.
"""
from __future__ import annotations

import datetime as _dt
import threading
from typing import Any, Callable, TypeVar

_T = TypeVar("_T")


class SessionHolder:
    def __init__(self, *, client: Any, host: str, user: str,
                  keepalive_interval: int = 30) -> None:
        self.client = client
        self.host = host
        self.user = user
        self.transport = client.get_transport()
        if self.transport is not None:
            self.transport.set_keepalive(keepalive_interval)
        # Eager open — default state holds SFTP.
        self._sftp = client.open_sftp()
        self._lock = threading.Lock()
        self.connected_at = _dt.datetime.now(_dt.timezone.utc).isoformat()

    # ── Public API ─────────────────────────────────────────────

    def is_alive(self) -> bool:
        return bool(self.transport and self.transport.is_active())

    def with_sftp(self, fn: Callable[[Any], _T]) -> _T:
        """Run fn(sftp) holding the channel mutex. Lazily reopens
        the SFTP channel if a previous exec closed it."""
        with self._lock:
            if self._sftp is None:
                self._sftp = self.client.open_sftp()
            return fn(self._sftp)

    def exec_command(self, command: str, timeout: float = 60.0
                      ) -> dict[str, Any]:
        """Close SFTP (if open), open an exec channel, run command,
        return {stdout_bytes, stderr_bytes, exit_code}. Leaves SFTP
        closed; the next with_sftp() reopens it."""
        with self._lock:
            # Free the single session slot for the exec channel.
            if self._sftp is not None:
                try:
                    self._sftp.close()
                except Exception:
                    pass
                self._sftp = None
            channel = self.transport.open_session()
            try:
                channel.settimeout(timeout)
                channel.exec_command(command)
                stdout_bytes = channel.makefile("rb").read()
                stderr_bytes = channel.makefile_stderr("rb").read()
                exit_code = channel.recv_exit_status()
            finally:
                try:
                    channel.close()
                except Exception:
                    pass
            return {
                "stdout_bytes": stdout_bytes,
                "stderr_bytes": stderr_bytes,
                "exit_code": exit_code,
            }

    def close(self) -> None:
        """Best-effort shutdown: close SFTP (if any) then client."""
        with self._lock:
            if self._sftp is not None:
                try:
                    self._sftp.close()
                except Exception:
                    pass
                self._sftp = None
            try:
                self.client.close()
            except Exception:
                pass
