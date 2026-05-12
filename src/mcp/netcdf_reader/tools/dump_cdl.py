# src/mcp/netcdf_reader/tools/dump_cdl.py
"""⤴ format-agnostic — eligible for _core/ lift.

dump_cdl() — emit CDL text (the standard NetCDF textual format
that ncdump and `ncks --cdl` produce). The output is semantically
equivalent to ncks --cdl: same variables, same dims, same
attributes, same data values. Exact whitespace and float
formatting may differ.

  * variables=None → all vars (data + coords)
  * variables=[...] → restrict (ncks -v parity)
  * header_only=True → omit the `data:` section (ncks -m / ncdump -h)
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from src.mcp.netcdf_reader import envelope
from src.mcp.netcdf_reader.paths.classify import ClassifyError, classify

if TYPE_CHECKING:
    from src.mcp.netcdf_reader.protocols import FormatAdapter


# numpy dtype → CDL type spelling
_CDL_TYPE = {
    "int8": "byte",
    "uint8": "ubyte",
    "int16": "short",
    "uint16": "ushort",
    "int32": "int",
    "uint32": "uint",
    "int64": "int64",
    "uint64": "uint64",
    "float32": "float",
    "float64": "double",
}


def _cdl_type(dtype: np.dtype) -> str:
    name = dtype.name
    if name in _CDL_TYPE:
        return _CDL_TYPE[name]
    if dtype.kind in ("U", "S"):
        return "string"
    if dtype.kind == "O":
        return "string"
    return name  # fall through — surface whatever it is


def _format_attr_value(val: Any) -> str:
    """Render an attribute value the CDL way:
       strings → "..."; arrays → 1, 2, 3; scalars → as-is."""
    # Strings (Python or numpy)
    if isinstance(val, (str, np.str_)):
        # CDL escapes: backslash, quote, newline. ncdump uses \" \\ \n
        s = str(val).replace("\\", "\\\\").replace('"', '\\"')
        s = s.replace("\n", "\\n")
        return f'"{s}"'
    if isinstance(val, bytes):
        return _format_attr_value(val.decode("utf-8", errors="replace"))
    # Numeric arrays / lists
    arr = np.asarray(val)
    if arr.ndim == 0:
        item = arr.item()
        if isinstance(item, float):
            return repr(item)
        if isinstance(item, (bytes, str)):
            return _format_attr_value(item)
        return str(item)
    parts = [_format_attr_value(v) for v in arr.ravel().tolist()]
    return ", ".join(parts)


def _format_data_values(arr: np.ndarray) -> str:
    """Flatten to a comma-separated CDL data section."""
    if arr.size == 0:
        return ""
    flat = arr.ravel()
    if arr.dtype.kind in ("U", "S", "O"):
        return ", ".join(
            _format_attr_value(v) for v in flat.tolist())
    if arr.dtype.kind == "f":
        # CDL uses the full-precision repr for round-trip safety.
        return ", ".join(repr(float(v)) for v in flat.tolist())
    return ", ".join(str(int(v)) for v in flat.tolist())


def _emit_dimensions(ds, indent: str = "\t") -> list[str]:
    out = ["dimensions:"]
    for name, size in ds.sizes.items():
        out.append(f"{indent}{name} = {int(size)} ;")
    return out


def _emit_variables(ds, var_names: list[str],
                    indent: str = "\t") -> list[str]:
    out = ["variables:"]
    for name in var_names:
        da = ds[name]
        ctype = _cdl_type(da.dtype)
        dims_str = ", ".join(str(d) for d in da.dims)
        out.append(f"{indent}{ctype} {name}({dims_str}) ;")
        # Attributes
        for k, v in da.attrs.items():
            out.append(f"{indent}{indent}{name}:{k} = "
                       f"{_format_attr_value(v)} ;")
    return out


def _emit_global_attrs(ds, indent: str = "\t") -> list[str]:
    if not ds.attrs:
        return []
    out = ["", "// global attributes:"]
    for k, v in ds.attrs.items():
        out.append(f"{indent}:{k} = {_format_attr_value(v)} ;")
    return out


def _emit_data(ds, var_names: list[str], indent: str = " ") -> list[str]:
    out = ["data:", ""]
    for name in var_names:
        values = ds[name].values
        body = _format_data_values(values)
        out.append(f"{indent}{name} = {body} ;")
        out.append("")
    return out


def dump_cdl(
    path: str,
    *,
    variables: list[str] | None = None,
    header_only: bool = False,
    adapter: FormatAdapter,
    ssh_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
        # Variable selection. Default: all data_vars then coords
        # (in that order — matches ncdump grouping conventions).
        if variables is not None:
            for v in variables:
                if v not in ds.variables:
                    return envelope.error(
                        "invalid_spec",
                        f"unknown variable in filter: {v!r}",
                        context={"available": list(ds.variables)})
            var_names = list(variables)
        else:
            var_names = list(ds.data_vars) + [
                str(c) for c in ds.coords if c not in ds.data_vars]

        # Derive a display name (the file's stem).
        from pathlib import Path as _P
        name = _P(path).stem or "dataset"

        lines: list[str] = [f"netcdf {name} {{"]
        lines.extend(_emit_dimensions(ds))
        lines.append("")
        lines.extend(_emit_variables(ds, var_names))
        lines.extend(_emit_global_attrs(ds))
        if not header_only:
            lines.append("")
            lines.extend(_emit_data(ds, var_names))
        lines.append("}")
        cdl = "\n".join(lines) + "\n"
        return envelope.success({"cdl": cdl})
    finally:
        ds.close()
