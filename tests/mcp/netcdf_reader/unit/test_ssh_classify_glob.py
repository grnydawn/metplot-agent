"""ssh://host/path/*.nc expands via the broker; raises broker_required without."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.mcp.netcdf_reader.paths.classify import (
    ClassifyError, PathKind, classify,
)


def test_ssh_url_without_glob_still_returns_ssh_remote():
    k = classify("ssh://host/path/file.nc")
    assert k.kind == PathKind.SSH_REMOTE


def test_ssh_glob_calls_broker_and_returns_ssh_multi():
    broker = MagicMock()
    broker.glob_remote.return_value = ["/data/a.nc", "/data/b.nc"]
    with patch("src.mcp.netcdf_reader.paths.ssh."
                "open_ssh_with_broker_fallback",
                return_value=broker):
        k = classify("ssh://host/data/*.nc")
    assert k.kind == PathKind.SSH_MULTI
    assert k.host == "host"
    assert k.paths == [
        "ssh://host/data/a.nc",
        "ssh://host/data/b.nc",
    ]
    broker.glob_remote.assert_called_with("/data/*.nc")


def test_ssh_glob_with_user_prefix_preserved():
    broker = MagicMock()
    broker.glob_remote.return_value = ["/data/a.nc"]
    with patch("src.mcp.netcdf_reader.paths.ssh."
                "open_ssh_with_broker_fallback",
                return_value=broker):
        k = classify("ssh://alice@host:2222/data/*.nc")
    assert k.kind == PathKind.SSH_MULTI
    assert k.paths == ["ssh://alice@host:2222/data/a.nc"]


def test_ssh_glob_without_broker_raises_broker_required():
    with patch("src.mcp.netcdf_reader.paths.ssh."
                "open_ssh_with_broker_fallback", return_value=None):
        with pytest.raises(ClassifyError) as ei:
            classify("ssh://host/data/*.nc")
        msg = str(ei.value)
        assert "broker_required" in msg
        assert "metplot-ssh-broker host" in msg


def test_ssh_glob_empty_matches_raises_clean_error():
    broker = MagicMock()
    broker.glob_remote.return_value = []
    with patch("src.mcp.netcdf_reader.paths.ssh."
                "open_ssh_with_broker_fallback", return_value=broker):
        with pytest.raises(ClassifyError) as ei:
            classify("ssh://host/data/*.nc")
        assert "no remote files matched" in str(ei.value)
