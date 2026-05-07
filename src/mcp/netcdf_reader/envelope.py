# src/mcp/netcdf-reader/envelope.py
"""⤴ format-agnostic — eligible for _core/ lift.

Response-envelope helpers and code taxonomies. Every tool returns one
of three envelope shapes: success, error, or ambiguity (the last is
itself an error envelope with code='ambiguous' and a list of candidates).
"""
from __future__ import annotations

from typing import Any


def success(
    result: dict[str, Any],
    *,
    warnings: list[dict[str, Any]] | None = None,
    resolved: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "result": result,
        "warnings": warnings or [],
        "resolved": resolved or {},
    }


def error(
    code: str,
    message: str,
    *,
    context: dict[str, Any] | None = None,
    warnings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {"code": code, "message": message, "context": context or {}},
        "warnings": warnings or [],
    }


def ambiguous(
    subcode: str,
    message: str,
    *,
    candidates: list[dict[str, Any]],
    prompt: str,
    retry_with_param: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": "ambiguous",
            "subcode": subcode,
            "message": message,
            "candidates": candidates,
            "prompt": prompt,
            "retry_with_param": retry_with_param,
            "context": context or {},
        },
        "warnings": [],
    }


def warn(code: str, message: str, *, context: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"code": code, "message": message, "context": context or {}}
