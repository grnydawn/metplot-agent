"""Smoke test for the inproc_sshd fixture.

If this passes, later integration tests can rely on the fixture
to accept paramiko clients for SFTP + exec.
"""
from __future__ import annotations

import paramiko


def test_inproc_sshd_password_auth_succeeds(inproc_sshd):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname="127.0.0.1", port=inproc_sshd.port,
                    username="testuser", password="testpass",
                    allow_agent=False, look_for_keys=False)
    sftp = client.open_sftp()
    names = sftp.listdir(inproc_sshd.root)
    assert "alpha.nc" in names
    assert "beta.nc" in names
    sftp.close()
    client.close()


def test_inproc_sshd_password_auth_rejects_bad_pass(inproc_sshd):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    with __import__("pytest").raises(paramiko.AuthenticationException):
        client.connect(hostname="127.0.0.1", port=inproc_sshd.port,
                        username="testuser", password="nope",
                        allow_agent=False, look_for_keys=False)


def test_inproc_sshd_exec_ncdump_returns_stub_cdl(inproc_sshd):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname="127.0.0.1", port=inproc_sshd.port,
                    username="testuser", password="testpass",
                    allow_agent=False, look_for_keys=False)
    transport = client.get_transport()
    chan = transport.open_session()
    chan.exec_command(f"ncdump -h {inproc_sshd.root}/alpha.nc")
    stdout = chan.makefile("rb").read().decode("utf-8")
    exit_code = chan.recv_exit_status()
    chan.close()
    client.close()
    assert "netcdf alpha" in stdout
    assert exit_code == 0


def test_inproc_sshd_exec_ncks_reports_command_not_found(inproc_sshd):
    """The fixture emulates a remote host where ncks isn't installed."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname="127.0.0.1", port=inproc_sshd.port,
                    username="testuser", password="testpass",
                    allow_agent=False, look_for_keys=False)
    transport = client.get_transport()
    chan = transport.open_session()
    chan.exec_command(f"ncks -m {inproc_sshd.root}/alpha.nc")
    stderr = chan.makefile_stderr("rb").read().decode("utf-8")
    exit_code = chan.recv_exit_status()
    chan.close()
    client.close()
    assert "command not found" in stderr or "ncks" in stderr
    assert exit_code == 127


def test_inproc_sshd_exec_unknown_command_returns_127(inproc_sshd):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname="127.0.0.1", port=inproc_sshd.port,
                    username="testuser", password="testpass",
                    allow_agent=False, look_for_keys=False)
    transport = client.get_transport()
    chan = transport.open_session()
    chan.exec_command("some_unknown_tool arg1")
    exit_code = chan.recv_exit_status()
    chan.close()
    client.close()
    assert exit_code == 127
