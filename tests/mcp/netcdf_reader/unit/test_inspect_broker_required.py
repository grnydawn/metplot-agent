"""inspect() returns broker_required envelope when ssh-glob hits no broker."""
from __future__ import annotations

from unittest.mock import patch

from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.inspect import inspect as _inspect


def test_inspect_returns_broker_required_envelope():
    """No broker → ssh-glob raises ClassifyError starting with
    broker_required: → inspect catches it and emits the structured
    envelope."""
    with patch("src.mcp.netcdf_reader.paths.ssh."
                "open_ssh_with_broker_fallback", return_value=None):
        env = _inspect(adapter=NetCDFAdapter(),
                        path="ssh://home.example/data/*.nc")
    assert env["ok"] is False
    assert env["error"]["code"] == "ambiguous"
    assert env["error"]["subcode"] == "broker_required"
    assert "metplot-ssh-broker home.example" in env["error"]["prompt"]
    assert env["error"]["context"]["host"] == "home.example"
