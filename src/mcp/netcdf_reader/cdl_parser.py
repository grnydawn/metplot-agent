"""Minimal CDL (NetCDF textual format) parser for ncdump -h output.

Parses the structure of an ncdump -h dump into a shallow envelope-
compatible dict. NOT a full CDL parser — only the bits we need to
populate `inspect()` envelopes from a header-only round-trip:

  - file basename
  - dimensions: list of {name, size, unlimited}
  - variables: list of {name, type, dim_names, attrs (subset)}
  - global_attrs: dict[str, str | int | float]

Anything we can't parse (data section, fancy types, escapes) is
silently skipped — the caller falls back to the full
`get_full → xarray.open_dataset` path on parse failure.

CDL grammar (simplified, ncdump -h output):

    netcdf <name> {
    [dimensions:
        <name> = <int_or_UNLIMITED> ;
        ...
    ]
    [variables:
        <type> <name>([<dim>, <dim>, ...]) ;
        [    <name>:<attr> = <value> ;
        ...]
    ]
    [// global attributes:
        :<attr> = <value> ;
    ]
    }
"""
from __future__ import annotations

import re
from typing import Any


class CDLParseError(Exception):
    pass


_RE_HEADER = re.compile(r"^netcdf\s+([^\s{]+)\s*\{")
_RE_DIM = re.compile(r"^\s*(\w+)\s*=\s*(UNLIMITED|\d+)")
_RE_VAR = re.compile(
    r"^\s*(byte|ubyte|char|short|ushort|int|uint|int64|uint64|"
    r"float|double|string)\s+(\w+)\s*(\(([^)]*)\))?\s*;"
)
_RE_ATTR = re.compile(r"^\s*(\w*):(\w+)\s*=\s*(.+)\s*;")
_RE_GLOBAL_ATTR = re.compile(r"^\s*:(\w+)\s*=\s*(.+)\s*;")


def _strip_value(raw: str) -> Any:
    """Best-effort literal scrub: strip trailing ; and one set of quotes."""
    s = raw.strip().rstrip(";").strip()
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1]
    # numeric?
    try:
        if "." in s or "e" in s.lower():
            return float(s.rstrip("f").rstrip("d"))
        return int(s)
    except ValueError:
        return s  # leave as string


def parse_cdl(text: str) -> dict[str, Any]:
    """Parse ncdump -h output. Returns:
        {
          "name": str,
          "dimensions": [{"name": str, "size": int | None,
                          "unlimited": bool}, ...],
          "variables": [{"name": str, "type": str,
                          "dim_names": [str, ...],
                          "attrs": {attr: value, ...}}, ...],
          "global_attrs": {attr: value, ...},
        }
    Raises CDLParseError if the input doesn't start with `netcdf X {`."""
    if not text or not text.strip():
        raise CDLParseError("empty CDL text")

    lines = text.splitlines()
    # 1. Header
    name = None
    for idx, line in enumerate(lines):
        m = _RE_HEADER.match(line.strip())
        if m:
            name = m.group(1)
            start = idx + 1
            break
    if name is None:
        raise CDLParseError(
            f"no 'netcdf <name> {{' header in first lines: "
            f"{lines[:3]!r}"
        )

    section = None  # None | "dimensions" | "variables" | "global"
    dimensions: list[dict[str, Any]] = []
    variables: list[dict[str, Any]] = []
    global_attrs: dict[str, Any] = {}
    current_var: dict[str, Any] | None = None

    for line in lines[start:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            # Could be a section marker or just a comment.
            if "global attributes:" in stripped:
                section = "global"
                current_var = None
            continue
        if stripped == "}":
            break
        if stripped.startswith("dimensions:"):
            section = "dimensions"
            current_var = None
            continue
        if stripped.startswith("variables:"):
            section = "variables"
            current_var = None
            continue
        if stripped.startswith("data:"):
            # We stop here — header-only.
            break

        if section == "dimensions":
            m = _RE_DIM.match(stripped)
            if m:
                name_d = m.group(1)
                val = m.group(2)
                if val == "UNLIMITED":
                    dimensions.append({"name": name_d, "size": None,
                                        "unlimited": True})
                else:
                    dimensions.append({"name": name_d, "size": int(val),
                                        "unlimited": False})
            continue

        if section == "variables":
            # First try: per-variable attribute line "<var>:<attr> = <val>"
            m_attr = _RE_ATTR.match(stripped)
            if m_attr and m_attr.group(1):
                # ":<attr>" with empty var → global attr (but we only
                # land here if section is variables — sometimes ncdump
                # emits globals without a heading)
                var_part = m_attr.group(1)
                if current_var is not None and current_var["name"] == var_part:
                    current_var["attrs"][m_attr.group(2)] = _strip_value(
                        m_attr.group(3))
                    continue

            # Then try: variable declaration
            m_var = _RE_VAR.match(stripped)
            if m_var:
                dim_str = m_var.group(4) or ""
                dim_names = [d.strip() for d in dim_str.split(",")
                              if d.strip()]
                current_var = {
                    "name": m_var.group(2),
                    "type": m_var.group(1),
                    "dim_names": dim_names,
                    "attrs": {},
                }
                variables.append(current_var)
                continue
            continue

        if section == "global":
            m_g = _RE_GLOBAL_ATTR.match(stripped)
            if m_g:
                global_attrs[m_g.group(1)] = _strip_value(m_g.group(2))

    return {
        "name": name,
        "dimensions": dimensions,
        "variables": variables,
        "global_attrs": global_attrs,
    }
