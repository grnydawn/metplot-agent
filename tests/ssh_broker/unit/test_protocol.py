"""JSON-RPC 2.0 wire-format primitives for the metplot-ssh-broker."""
from __future__ import annotations

import json

import pytest

from src.ssh_broker.protocol import (
    CONNECTION_LOST, INTERNAL_ERROR, INVALID_PARAMS, JSONRPC_VERSION,
    METHOD_NOT_FOUND, PARSE_ERROR, SFTP_ERROR, TOOL_NOT_FOUND,
    TOOL_NOT_IN_ALLOWLIST, decode_line, encode_message, make_error,
    make_request, make_response,
)


def test_make_request_shape():
    r = make_request(req_id=7, method="listdir", params={"path": "/x"})
    assert r["jsonrpc"] == JSONRPC_VERSION
    assert r["id"] == 7
    assert r["method"] == "listdir"
    assert r["params"] == {"path": "/x"}


def test_make_request_defaults_params_to_empty_dict():
    r = make_request(req_id=1, method="ping")
    assert r["params"] == {}


def test_make_response_shape():
    r = make_response(req_id=3, result={"ok": True})
    assert r["jsonrpc"] == JSONRPC_VERSION
    assert r["id"] == 3
    assert r["result"] == {"ok": True}
    assert "error" not in r


def test_make_error_shape():
    r = make_error(req_id=4, code=METHOD_NOT_FOUND, message="unknown method 'foo'")
    assert r["jsonrpc"] == JSONRPC_VERSION
    assert r["id"] == 4
    assert r["error"] == {"code": METHOD_NOT_FOUND, "message": "unknown method 'foo'"}
    assert "result" not in r


def test_encode_appends_newline_and_utf8():
    line = encode_message(make_request(1, "ping"))
    assert isinstance(line, bytes)
    assert line.endswith(b"\n")
    obj = json.loads(line.decode("utf-8"))
    assert obj["method"] == "ping"


def test_encode_uses_compact_separators():
    line = encode_message({"a": 1, "b": [2, 3]})
    assert b" " not in line


def test_decode_parses_valid_json():
    obj = decode_line(b'{"a":1}\n')
    assert obj == {"a": 1}


def test_decode_strips_trailing_newline():
    obj = decode_line(b'{"a":1}')
    assert obj == {"a": 1}


def test_decode_raises_on_malformed():
    with pytest.raises(json.JSONDecodeError):
        decode_line(b'not json')


def test_standard_jsonrpc_error_codes():
    # https://www.jsonrpc.org/specification#error_object
    assert PARSE_ERROR == -32700
    assert METHOD_NOT_FOUND == -32601
    assert INVALID_PARAMS == -32602
    assert INTERNAL_ERROR == -32603


def test_broker_specific_error_codes():
    # Server-error range -32000..-32099, broker-specific assignments
    assert CONNECTION_LOST == -32000
    assert SFTP_ERROR == -32001
    assert TOOL_NOT_FOUND == -32002
    assert TOOL_NOT_IN_ALLOWLIST == -32003
