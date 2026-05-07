from unittest.mock import MagicMock, patch
import pytest
import paramiko
from src.mcp.netcdf_reader.paths.ssh import (
    SSHConfig, connect_explicit, SSHAuthFailed,
)


def test_connect_with_password():
    cfg = SSHConfig(host="h", user="u", password="secret")
    fake = MagicMock()
    with patch("paramiko.SSHClient", return_value=fake):
        connect_explicit(cfg)
        fake.connect.assert_called_once()
        kwargs = fake.connect.call_args.kwargs
        assert kwargs["password"] == "secret"
        assert kwargs["username"] == "u"


def test_connect_with_identity_and_passphrase():
    cfg = SSHConfig(host="h", user="u",
                    identity_file="/k/key", passphrase="ppp")
    fake = MagicMock()
    with patch("paramiko.SSHClient", return_value=fake):
        connect_explicit(cfg)
        kwargs = fake.connect.call_args.kwargs
        assert kwargs["key_filename"] == "/k/key"
        assert kwargs["passphrase"] == "ppp"


def test_connect_failed_raises_ssh_auth_failed():
    cfg = SSHConfig(host="h", user="u", password="wrong")
    fake = MagicMock()
    fake.connect.side_effect = paramiko.AuthenticationException("denied")
    with patch("paramiko.SSHClient", return_value=fake):
        with pytest.raises(SSHAuthFailed):
            connect_explicit(cfg)


def test_password_not_logged(caplog):
    cfg = SSHConfig(host="h", user="u", password="hunter2")
    fake = MagicMock()
    fake.connect.side_effect = paramiko.AuthenticationException("denied")
    with patch("paramiko.SSHClient", return_value=fake):
        try:
            connect_explicit(cfg)
        except SSHAuthFailed:
            pass
    assert "hunter2" not in caplog.text
