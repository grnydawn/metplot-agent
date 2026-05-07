from src.mcp.plot_renderer.defaults import LIBRARY_DEFAULTS


def test_library_defaults_shape():
    # Required fields present per spec §4.3
    required = {
        "colormap", "projection", "colorbar_position", "gridlines",
        "font_scale", "aspect", "dpi", "format", "downsample", "log_scale",
    }
    assert required.issubset(LIBRARY_DEFAULTS.keys())


def test_library_defaults_values():
    assert LIBRARY_DEFAULTS["colormap"] == "viridis"
    assert LIBRARY_DEFAULTS["projection"] == "PlateCarree"
    assert LIBRARY_DEFAULTS["dpi"] == 150
    assert LIBRARY_DEFAULTS["format"] == "png"
    assert LIBRARY_DEFAULTS["downsample"] is True


def test_library_defaults_immutable():
    # Defending against accidental mutation in code under test
    import copy
    snapshot = copy.deepcopy(LIBRARY_DEFAULTS)
    LIBRARY_DEFAULTS["colormap"] = "tab10"
    try:
        assert LIBRARY_DEFAULTS != snapshot   # mutation took effect
    finally:
        LIBRARY_DEFAULTS["colormap"] = snapshot["colormap"]
