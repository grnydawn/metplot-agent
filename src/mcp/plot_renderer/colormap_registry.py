"""⤴ format-agnostic — eligible for _core/ lift.

Lazy-loaded matplotlib colormap registry wrapper. Centralizes cmap
validation so style.py / safety.py / tools/* can check without each
importing matplotlib.cm directly.
"""
from __future__ import annotations


class UnknownColormapError(ValueError):
    pass


def _registry() -> set[str]:
    # Lazy import: matplotlib loads on first call only.
    import matplotlib as mpl
    return set(mpl.colormaps)


def is_known_cmap(name: str) -> bool:
    return name in _registry()


def validate_cmap_name(name: str) -> None:
    if not is_known_cmap(name):
        raise UnknownColormapError(
            f"colormap {name!r} is not in matplotlib's registry")
