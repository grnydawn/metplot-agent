from unittest.mock import MagicMock, patch
from src.mcp.netcdf_reader.paths.ssh import (
    SSHConfig, ConnectionPool,
)


def test_pool_returns_same_client_for_same_host():
    pool = ConnectionPool()
    cfg = SSHConfig(host="h", port=22, user="u")
    fake = MagicMock()
    with patch("src.mcp.netcdf_reader.paths.ssh.connect_explicit",
               return_value=fake) as connect:
        c1 = pool.get_or_open(cfg)
        c2 = pool.get_or_open(cfg)
        assert c1 is c2
        connect.assert_called_once()


def test_pool_separates_different_user_or_host():
    pool = ConnectionPool()
    fake_a, fake_b = MagicMock(), MagicMock()
    with patch("src.mcp.netcdf_reader.paths.ssh.connect_explicit",
               side_effect=[fake_a, fake_b]):
        c1 = pool.get_or_open(SSHConfig(host="h1", user="u"))
        c2 = pool.get_or_open(SSHConfig(host="h2", user="u"))
        assert c1 is not c2


def test_pool_close_all_calls_each_close():
    pool = ConnectionPool()
    fakes = [MagicMock(), MagicMock()]
    with patch("src.mcp.netcdf_reader.paths.ssh.connect_explicit",
               side_effect=fakes):
        pool.get_or_open(SSHConfig(host="h1", user="u"))
        pool.get_or_open(SSHConfig(host="h2", user="u"))
    pool.close_all()
    for f in fakes:
        f.close.assert_called_once()
    assert len(pool._pool) == 0


def test_pool_zeros_credentials_on_close():
    pool = ConnectionPool()
    cfg = SSHConfig(host="h", user="u", password="hunter2")
    fake = MagicMock()
    with patch("src.mcp.netcdf_reader.paths.ssh.connect_explicit",
               return_value=fake):
        pool.get_or_open(cfg)
        pool.close_all()
    # The stored cfg's password field should be cleared
    assert cfg.password is None or cfg.password == ""
