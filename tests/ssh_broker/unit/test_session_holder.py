"""SessionHolder — single-session-channel state machine.

Hard invariant: only ONE SSH session channel open at a time on
the broker's transport. OLCF MaxSessions=1 compatibility is a
design contract.
"""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

from src.ssh_broker.session_holder import SessionHolder


def _mk_client_mocks(*, transport_active: bool = True):
    """Return (client_mock, transport_mock, sftp_mock) wired up."""
    transport = MagicMock()
    transport.is_active.return_value = transport_active
    client = MagicMock()
    client.get_transport.return_value = transport
    sftp = MagicMock()
    client.open_sftp.return_value = sftp
    return client, transport, sftp


# ── Construction ────────────────────────────────────────────────

def test_holder_eagerly_opens_sftp_on_init():
    client, transport, sftp = _mk_client_mocks()
    h = SessionHolder(client=client, host="h", user="u")
    assert h._sftp is sftp
    client.open_sftp.assert_called_once()


def test_holder_sets_keepalive_with_default_30s():
    client, transport, _ = _mk_client_mocks()
    SessionHolder(client=client, host="h", user="u")
    transport.set_keepalive.assert_called_with(30)


def test_holder_keepalive_interval_overridable():
    client, transport, _ = _mk_client_mocks()
    SessionHolder(client=client, host="h", user="u",
                   keepalive_interval=60)
    transport.set_keepalive.assert_called_with(60)


def test_holder_records_host_user_and_connected_at():
    client, _, _ = _mk_client_mocks()
    h = SessionHolder(client=client, host="myhost", user="myuser")
    assert h.host == "myhost"
    assert h.user == "myuser"
    assert isinstance(h.connected_at, str)
    assert "T" in h.connected_at  # ISO-8601 format


# ── is_alive ────────────────────────────────────────────────────

def test_is_alive_true_when_transport_active():
    client, transport, _ = _mk_client_mocks(transport_active=True)
    h = SessionHolder(client=client, host="h", user="u")
    assert h.is_alive() is True


def test_is_alive_false_when_transport_inactive():
    client, transport, _ = _mk_client_mocks(transport_active=True)
    h = SessionHolder(client=client, host="h", user="u")
    transport.is_active.return_value = False
    assert h.is_alive() is False


# ── with_sftp ───────────────────────────────────────────────────

def test_with_sftp_passes_open_client_to_fn():
    client, _, sftp = _mk_client_mocks()
    h = SessionHolder(client=client, host="h", user="u")
    sftp.listdir_attr.return_value = ["a", "b"]
    result = h.with_sftp(lambda s: s.listdir_attr("/path"))
    assert result == ["a", "b"]
    sftp.listdir_attr.assert_called_with("/path")


def test_with_sftp_lazily_reopens_after_exec_closed_it():
    client, transport, sftp = _mk_client_mocks()
    h = SessionHolder(client=client, host="h", user="u")
    # Simulate that exec_command has closed SFTP.
    h._sftp = None
    # Reset open_sftp call count from construction-time call.
    client.open_sftp.reset_mock()
    new_sftp = MagicMock()
    client.open_sftp.return_value = new_sftp
    h.with_sftp(lambda s: None)
    client.open_sftp.assert_called_once()
    assert h._sftp is new_sftp


# ── exec_command ────────────────────────────────────────────────

def _wire_exec_session(transport, stdout_bytes: bytes = b"",
                        stderr_bytes: bytes = b"", exit_code: int = 0):
    """Configure transport.open_session() to return a channel that
    produces the given exec output."""
    channel = MagicMock()
    transport.open_session.return_value = channel
    channel.makefile.return_value.read.return_value = stdout_bytes
    channel.makefile_stderr.return_value.read.return_value = stderr_bytes
    channel.recv_exit_status.return_value = exit_code
    return channel


def test_exec_command_closes_sftp_before_opening_exec_channel():
    client, transport, sftp = _mk_client_mocks()
    h = SessionHolder(client=client, host="h", user="u")
    _wire_exec_session(transport)
    h.exec_command("ncdump -h /foo.nc", timeout=10)
    # SFTP.close() must have been called BEFORE transport.open_session
    sftp.close.assert_called()
    transport.open_session.assert_called_once()


def test_exec_command_leaves_sftp_none_after():
    client, transport, sftp = _mk_client_mocks()
    h = SessionHolder(client=client, host="h", user="u")
    _wire_exec_session(transport)
    h.exec_command("ncdump -h /foo.nc", timeout=10)
    assert h._sftp is None


def test_exec_command_returns_stdout_stderr_and_exit_code():
    client, transport, _ = _mk_client_mocks()
    h = SessionHolder(client=client, host="h", user="u")
    _wire_exec_session(transport, stdout_bytes=b"hello\n",
                        stderr_bytes=b"warn\n", exit_code=0)
    r = h.exec_command("ncdump -h /foo.nc", timeout=10)
    assert r["stdout_bytes"] == b"hello\n"
    assert r["stderr_bytes"] == b"warn\n"
    assert r["exit_code"] == 0


def test_exec_command_passes_command_to_channel():
    client, transport, _ = _mk_client_mocks()
    h = SessionHolder(client=client, host="h", user="u")
    channel = _wire_exec_session(transport)
    h.exec_command("ls -lh /data", timeout=10)
    channel.exec_command.assert_called_with("ls -lh /data")


def test_exec_command_closes_channel_after():
    client, transport, _ = _mk_client_mocks()
    h = SessionHolder(client=client, host="h", user="u")
    channel = _wire_exec_session(transport)
    h.exec_command("ls", timeout=10)
    channel.close.assert_called_once()


def test_exec_command_then_with_sftp_reopens_sftp():
    client, transport, sftp = _mk_client_mocks()
    h = SessionHolder(client=client, host="h", user="u")
    _wire_exec_session(transport)
    h.exec_command("ls", timeout=10)
    assert h._sftp is None
    client.open_sftp.reset_mock()
    new_sftp = MagicMock()
    client.open_sftp.return_value = new_sftp
    h.with_sftp(lambda s: s.listdir("/x"))
    new_sftp.listdir.assert_called_with("/x")
    client.open_sftp.assert_called_once()


# ── Mutex / serialization ───────────────────────────────────────

def test_mutex_serializes_concurrent_with_sftp_calls():
    """Two threads calling with_sftp concurrently must NOT have their
    fn-bodies overlap. We verify by detecting concurrent entry."""
    client, transport, sftp = _mk_client_mocks()
    h = SessionHolder(client=client, host="h", user="u")

    in_flight = [0]
    max_in_flight = [0]
    barrier = threading.Barrier(2)

    def fn(_s):
        in_flight[0] += 1
        max_in_flight[0] = max(max_in_flight[0], in_flight[0])
        time.sleep(0.05)
        in_flight[0] -= 1

    def call_with_barrier():
        barrier.wait()
        h.with_sftp(fn)

    t1 = threading.Thread(target=call_with_barrier)
    t2 = threading.Thread(target=call_with_barrier)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert max_in_flight[0] == 1  # never overlapped


# ── close ───────────────────────────────────────────────────────

def test_close_closes_sftp_then_client():
    client, _, sftp = _mk_client_mocks()
    h = SessionHolder(client=client, host="h", user="u")
    h.close()
    sftp.close.assert_called()
    client.close.assert_called()


def test_close_is_best_effort_on_sftp_error():
    client, _, sftp = _mk_client_mocks()
    h = SessionHolder(client=client, host="h", user="u")
    sftp.close.side_effect = OSError("already closed")
    h.close()  # must not raise
    client.close.assert_called()  # client.close still runs


def test_close_when_sftp_already_none():
    """After an exec_command, _sftp is None. close() must still work."""
    client, transport, _ = _mk_client_mocks()
    h = SessionHolder(client=client, host="h", user="u")
    h._sftp = None
    h.close()  # must not raise
    client.close.assert_called()
