import pytest

from src.mcp.plot_renderer.colormap_registry import (
    is_known_cmap, validate_cmap_name, UnknownColormapError,
)


def test_known_cmap_returns_true():
    assert is_known_cmap("viridis") is True
    assert is_known_cmap("RdBu_r") is True
    assert is_known_cmap("tab10") is True


def test_unknown_cmap_returns_false():
    assert is_known_cmap("definitely_not_a_real_cmap") is False
    assert is_known_cmap("Rainbow") is False  # capital R; matplotlib has 'rainbow'


def test_validate_passes_for_known():
    validate_cmap_name("viridis")  # no exception


def test_validate_raises_unknown():
    with pytest.raises(UnknownColormapError) as exc:
        validate_cmap_name("not_a_cmap")
    assert "not_a_cmap" in str(exc.value)
