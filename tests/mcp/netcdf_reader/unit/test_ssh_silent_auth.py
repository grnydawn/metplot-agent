# tests/mcp/netcdf_reader/unit/test_ssh_silent_auth.py
from unittest.mock import MagicMock, patch

import paramiko
import pytest

from src.mcp.netcdf_reader.paths.ssh import (
    SSHConfig, AuthAttempt, silent_auth_chain, SSHAuthNeeded,
)


def paramiko_AuthenticationException(msg):
    return paramiko.AuthenticationException(msg)


def test_silent_auth_succeeds_with_agent_keys():
    cfg = SSHConfig(host="h", user="u")
    fake_client = MagicMock()
    with patch("paramiko.SSHClient") as MockClient, \
         patch.dict("os.environ", {"SSH_AUTH_SOCK": "/tmp/agent.sock"}):
        MockClient.return_value.connect.return_value = None
        MockClient.return_value = fake_client
        # First connect call (agent) succeeds
        client, attempts = silent_auth_chain(cfg)
        assert client is not None
        assert any(a.method == "ssh_agent" and a.result == "success"
                   for a in attempts)


def test_silent_auth_falls_through_and_raises_when_all_fail():
    cfg = SSHConfig(host="h", user="u")
    with patch("paramiko.SSHClient") as MockClient, \
         patch.dict("os.environ", {}, clear=True):
        # Every connect call raises AuthenticationException
        MockClient.return_value.connect.side_effect = (
            paramiko_AuthenticationException("nope")
        )
        with pytest.raises(SSHAuthNeeded) as excinfo:
            silent_auth_chain(cfg)
        attempts = excinfo.value.attempts
        # ssh-agent skipped (no SSH_AUTH_SOCK), default identities tried
        assert any(a.method == "default_identity_files" for a in attempts)
