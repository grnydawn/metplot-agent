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


class ErrorCode:
    FILE_NOT_FOUND = "file_not_found"
    REMOTE_FILE_NOT_FOUND = "remote_file_not_found"
    REMOTE_PERMISSION_DENIED = "remote_permission_denied"
    MULTI_FILE_COMBINE_FAILED = "multi_file_combine_failed"
    UNSUPPORTED_PATH_SCHEME = "unsupported_path_scheme"
    SSH_AUTH_FAILED = "ssh_auth_failed"
    SSH_TIMEOUT = "ssh_timeout"
    UNKNOWN_VARIABLE = "unknown_variable"
    OUT_OF_BOUNDS = "out_of_bounds"
    EMPTY_SLICE = "empty_slice"
    SIZE_LIMIT_EXCEEDED = "size_limit_exceeded"
    CONVENTION_TRANSFORM_UNAVAILABLE = "convention_transform_unavailable"
    NOT_4D = "not_4d"
    INTERNAL_ERROR = "internal_error"
    AMBIGUOUS = "ambiguous"
    UNSTRUCTURED_DYCORE_UNSUPPORTED = "unstructured_dycore_unsupported"


class AmbiguitySubcode:
    CONVENTION = "convention"
    VARIABLE = "variable"
    SSH_AUTH_NEEDED = "ssh_auth_needed"
    TIME_MATCH = "time_match"
    REGION = "region"
    MULTI_FILE_COMBINE = "multi_file_combine"
    MESH_PAIRING_REQUIRED = "mesh_pairing_required"
    BROKER_REQUIRED = "broker_required"


class WarningCode:
    SLOW_REMOTE_READ = "slow_remote_read"
    HIGH_NAN_FRACTION = "high_nan_fraction"
    CONSTANT_FIELD = "constant_field"
    NON_MONOTONIC_COORD = "non_monotonic_coord"
    NON_STANDARD_CALENDAR = "non_standard_calendar"
    PERCENTILE_CLIP_SUGGESTED = "percentile_clip_suggested"
    TIME_DECODE_FAILED = "time_decode_failed"
    DYCORE_VARS_PRESENT = "dycore_vars_present"
