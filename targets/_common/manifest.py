# targets/_common/manifest.py
"""Shared metadata constants used by every build target."""
from __future__ import annotations

from targets._common.skills import INCLUDED_SKILLS
from targets._common.mcp_bundling import MCP_SERVERS


PLUGIN_NAME = "ncplot-agent"
PLUGIN_VERSION = "0.1.0"
PLUGIN_DESCRIPTION = (
    "Natural-language plotting from NetCDF files. Maps, time series, "
    "and vertical profiles. WRF/ROMS/CMIP/reanalysis aware."
)
PLUGIN_HOMEPAGE = "https://github.com/grnydawn/ncplot-agent"
PLUGIN_LICENSE = "MIT"
PLUGIN_KEYWORDS = ["netcdf", "matplotlib", "cartopy", "wrf", "roms",
                    "cmip", "climate"]
PLUGIN_AUTHOR = {"name": "ncplot-agent contributors"}


def common_ncplot_block(build_cycle: int) -> dict:
    """Return the `ncplot` namespace block for embedding in any
    host-specific manifest. All host manifests carry this block for
    cross-target audit."""
    return {
        "build_cycle": build_cycle,
        "ships_skills": sorted(INCLUDED_SKILLS),
        "ships_mcp_servers": [s["external_name"] for s in MCP_SERVERS],
    }
