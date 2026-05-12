"""JSON-RPC 2.0 wire format for the metplot-ssh-broker.

Wire form: newline-delimited JSON over a UNIX domain socket.
Each line is one JSON object.

Request:   {"jsonrpc":"2.0","id":N,"method":"...","params":{...}}
Response:  {"jsonrpc":"2.0","id":N,"result":{...}}
Error:     {"jsonrpc":"2.0","id":N,"error":{"code":int,"message":str}}
"""
from __future__ import annotations

import json
from typing import Any, TypedDict

JSONRPC_VERSION = "2.0"

# Standard JSON-RPC 2.0 error codes (https://www.jsonrpc.org/specification)
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# Broker-specific error codes (-32000..-32099 is the "Server error" range)
CONNECTION_LOST = -32000
SFTP_ERROR = -32001
TOOL_NOT_FOUND = -32002
TOOL_NOT_IN_ALLOWLIST = -32003


class Request(TypedDict):
    jsonrpc: str
    id: int
    method: str
    params: dict[str, Any]


class ErrorPayload(TypedDict):
    code: int
    message: str


class Response(TypedDict, total=False):
    jsonrpc: str
    id: int
    result: dict[str, Any]
    error: ErrorPayload


def make_request(req_id: int, method: str,
                  params: dict[str, Any] | None = None) -> Request:
    return {"jsonrpc": JSONRPC_VERSION, "id": req_id, "method": method,
            "params": params or {}}


def make_response(req_id: int, result: dict[str, Any]) -> Response:
    return {"jsonrpc": JSONRPC_VERSION, "id": req_id, "result": result}


def make_error(req_id: int, code: int, message: str) -> Response:
    return {"jsonrpc": JSONRPC_VERSION, "id": req_id,
            "error": {"code": code, "message": message}}


def encode_message(msg: dict[str, Any]) -> bytes:
    """Serialize to a single newline-terminated UTF-8 line."""
    return (json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8")


def decode_line(line: bytes) -> dict[str, Any]:
    """Deserialize one newline-terminated line (newline optional)."""
    return json.loads(line.decode("utf-8").rstrip("\n"))
