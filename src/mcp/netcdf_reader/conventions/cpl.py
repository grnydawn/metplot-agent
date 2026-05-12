"""Format-specific (NetCDF): E3SM CPL (coupler) detection.

CPL files store coupler-internal mapping weights, domain
descriptions, and per-component history accumulations. Their
distinguishing fingerprint is dim names:

  - `dom[ailo]_n[xy]`: per-component (atm/lnd/ice/ocn) domain
    grid dims.
  - `[a-z]2[a-z]_[a-z]x_n[xy]`: component-to-coupler mapping
    axes (a2x = atm-to-coupler, o2x = ocn-to-coupler, etc.). The
    `ax`/`lx`/`ox`/`ix` infix is the per-component grid kind.

Detection-only in cycle 10. Most CPL variables are coupler
internals (mapping weights, fractions, budgets) that aren't
user-plottable. Spatial extraction + plotting is cycle 11+ scope.
"""
from __future__ import annotations

import re
from typing import Any

import xarray as xr

_CPL_MAPPING_RE = re.compile(r"^[a-z]2[a-z]_[a-z]x_n[xy]$")
_CPL_DOMAIN_RE = re.compile(r"^dom[ailo]_n[xy]$")


def detect(ds: xr.Dataset, attrs: dict[str, Any]) -> dict[str, Any] | None:
    dim_names = [str(d) for d in ds.dims]
    mapping_hits = [d for d in dim_names if _CPL_MAPPING_RE.match(d)]
    domain_hits = [d for d in dim_names if _CPL_DOMAIN_RE.match(d)]

    # Require ≥3 mapping-pattern hits OR ≥2 domain-pattern hits.
    # A single mapping dim alone could be a CIME-adjacent file
    # that happens to share the naming style.
    if len(mapping_hits) < 3 and len(domain_hits) < 2:
        return None

    evidence: list[str] = []
    if mapping_hits:
        evidence.append(
            f"CPL component-to-coupler mapping dims matched "
            f"({len(mapping_hits)} hits: {', '.join(mapping_hits[:5])}"
            + (f", … +{len(mapping_hits) - 5} more"
               if len(mapping_hits) > 5 else "")
            + ")")
    if domain_hits:
        evidence.append(
            f"CPL per-component domain dims matched "
            f"({len(domain_hits)} hits: {', '.join(domain_hits[:5])}"
            + (f", … +{len(domain_hits) - 5} more"
               if len(domain_hits) > 5 else "")
            + ")")

    # High confidence when:
    #   - both pattern classes fire, OR
    #   - a single class fires strongly (≥5 mapping hits, or ≥3
    #     domain hits — distinctive enough on its own).
    has_both = len(mapping_hits) >= 3 and len(domain_hits) >= 2
    strong_mapping = len(mapping_hits) >= 5
    strong_domain = len(domain_hits) >= 3
    confidence = ("high" if has_both or strong_mapping or strong_domain
                   else "medium")

    return {
        "primary": "CPL",
        "confidence": confidence,
        "evidence": evidence,
        "candidates": None,
    }
