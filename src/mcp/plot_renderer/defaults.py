"""⤴ format-agnostic — eligible for _core/ lift.

Library-level safe defaults. Domain knowledge (anomaly → RdBu_r etc.)
lives in cycle-3 skills, not here.
"""
from __future__ import annotations

LIBRARY_DEFAULTS: dict[str, object] = {
    "colormap":          "viridis",
    "projection":        "PlateCarree",
    "colorbar_position": "right",
    "gridlines":         "light",
    "font_scale":        1.0,
    "aspect":            "auto",
    "dpi":               150,
    "format":            "png",
    "downsample":        True,
    "log_scale":         False,    # render_profile may override to True
}
