from typing import Any

from src.mcp.plot_renderer.protocols import SliceLoader


class _DummyLoader:
    name = "dummy"
    supported_formats = {"netcdf"}

    def load(self, slice_ref: dict[str, Any]):
        return None


def test_dummy_loader_satisfies_protocol():
    assert isinstance(_DummyLoader(), SliceLoader)


def test_loader_missing_attr_fails_protocol():
    class Bad:
        pass
    assert not isinstance(Bad(), SliceLoader)
