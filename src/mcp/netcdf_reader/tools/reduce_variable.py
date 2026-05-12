# src/mcp/netcdf_reader/tools/reduce_variable.py
"""⤴ format-agnostic — eligible for _core/ lift.

reduce_variable() — collapse a variable along named dims via
one of {avg, min, max, sum, rms, total}. Ncks `-y` parity:

  * `total` is an ncks alias for `sum` — they produce
    identical output.
  * `rms` is sqrt(mean(x**2)) along the reduce axes.
  * `avg` uses np.mean (NaN-propagating); callers needing
    NaN-skipping should pre-clean.
  * `reduce_dims=[]` collapses every dim to a scalar.
  * Dim names matched case-insensitively against da.dims.

Output envelope: result.values, result.dims (remaining dims
in original order), result.shape, result.op, result.reduced_dims,
result.units.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from src.mcp.netcdf_reader import envelope
from src.mcp.netcdf_reader.paths.classify import ClassifyError, classify

if TYPE_CHECKING:
    from src.mcp.netcdf_reader.protocols import FormatAdapter


_SUPPORTED_OPS = frozenset({"avg", "min", "max", "sum", "rms", "total"})


def _apply_op(arr: np.ndarray, axes: tuple[int, ...] | None,
              op: str) -> np.ndarray:
    """Reduce arr along `axes` using `op`. axes=None → reduce all."""
    if op in ("avg",):
        return np.mean(arr, axis=axes)
    if op in ("sum", "total"):
        return np.sum(arr, axis=axes)
    if op == "min":
        return np.min(arr, axis=axes)
    if op == "max":
        return np.max(arr, axis=axes)
    if op == "rms":
        # sqrt(mean(x**2)) — single-pass on float64-promoted view.
        return np.sqrt(np.mean(arr.astype(np.float64, copy=False) ** 2,
                                axis=axes))
    raise ValueError(f"unsupported op: {op}")


def _to_json_safe(arr: np.ndarray) -> Any:
    """Convert ndarray to nested list with NaN → 'NaN'. Mirrors
    the read_slice helper so envelopes are consistent."""
    if arr.ndim == 0:
        v = arr.item()
        if isinstance(v, float) and np.isnan(v):
            return "NaN"
        return v
    out: list[Any] = []
    for sub in arr:
        out.append(_to_json_safe(np.asarray(sub)))
    return out


def reduce_variable(
    path: str,
    variable: str,
    reduce_dims: list[str],
    op: str,
    *,
    adapter: FormatAdapter,
    ssh_config: dict[str, Any] | None = None,
    mesh_path: str | None = None,
) -> dict[str, Any]:
    if op not in _SUPPORTED_OPS:
        return envelope.error(
            "invalid_spec",
            f"unsupported op {op!r}; expected one of "
            f"{sorted(_SUPPORTED_OPS)}",
            context={"op": op, "supported": sorted(_SUPPORTED_OPS)})
    if not isinstance(reduce_dims, list):
        return envelope.error(
            "invalid_spec",
            "reduce_dims must be a list of dim names (use [] to "
            "reduce all dims)",
            context={"reduce_dims": reduce_dims})

    try:
        cls = classify(path)
    except ClassifyError as e:
        return envelope.error(envelope.ErrorCode.FILE_NOT_FOUND, str(e),
                              context={"path": path})
    try:
        ds = adapter.open(cls.paths, ssh_config=ssh_config)
    except FileNotFoundError as e:
        return envelope.error(envelope.ErrorCode.FILE_NOT_FOUND, str(e),
                              context={"path": path})

    try:
        if variable not in ds.data_vars:
            return envelope.error(
                "invalid_spec",
                f"unknown variable: {variable!r}",
                context={"available": [str(n) for n in ds.data_vars]})

        da = ds[variable]
        var_dims = [str(d) for d in da.dims]
        # Resolve each requested reduce dim case-insensitively.
        resolved_dims: list[str] = []
        for rd in reduce_dims:
            actual = next((d for d in var_dims
                           if d.lower() == str(rd).lower()), None)
            if actual is None:
                return envelope.error(
                    "invalid_spec",
                    f"reduce_dims includes {rd!r} which is not a dim "
                    f"of variable {variable!r}",
                    context={"reduce_dim": rd, "var_dims": var_dims})
            if actual in resolved_dims:
                return envelope.error(
                    "invalid_spec",
                    f"duplicate reduce dim {actual!r}",
                    context={"reduce_dim": actual})
            resolved_dims.append(actual)

        # Empty list → reduce over all dims.
        if not resolved_dims:
            axes: tuple[int, ...] | None = None
            remaining: list[str] = []
        else:
            axes = tuple(var_dims.index(d) for d in resolved_dims)
            remaining = [d for d in var_dims if d not in resolved_dims]

        values = da.load().values
        reduced = _apply_op(values, axes, op)
        result = {
            "values": _to_json_safe(np.asarray(reduced)),
            "dims": remaining,
            "shape": list(np.asarray(reduced).shape),
            "op": op,
            "reduced_dims": resolved_dims,
            "units": ds[variable].attrs.get("units"),
        }
        return envelope.success(result)
    finally:
        ds.close()
