from unittest.mock import MagicMock, patch
from src.mcp.netcdf_reader.paths.ssh import open_sftp_file


def test_open_sftp_file_returns_handle():
    fake_client = MagicMock()
    fake_sftp = MagicMock()
    fake_handle = MagicMock()
    fake_client.open_sftp.return_value = fake_sftp
    fake_sftp.open.return_value = fake_handle
    h = open_sftp_file(fake_client, "/remote/x.nc")
    assert h is fake_handle
    fake_sftp.open.assert_called_with("/remote/x.nc", "rb")


def test_open_sftp_file_supports_random_access():
    """h5netcdf needs seek + tell + read on the file-like."""
    fake_client = MagicMock()
    fake_handle = MagicMock()
    fake_handle.read.return_value = b"data"
    fake_handle.tell.return_value = 0
    fake_client.open_sftp.return_value.open.return_value = fake_handle
    h = open_sftp_file(fake_client, "/x.nc")
    assert h.read(4) == b"data"
    h.seek(100)
    fake_handle.seek.assert_called_with(100)
