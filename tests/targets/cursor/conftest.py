# tests/targets/cursor/conftest.py
import importlib.util
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
BUILD_PY = REPO_ROOT / "targets" / "cursor" / "build.py"


def _load():
    spec = importlib.util.spec_from_file_location("targets.cursor.build", BUILD_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def built_plugin(tmp_path_factory):
    out = tmp_path_factory.mktemp("build-cursor")
    _load().build(SRC_ROOT, out)
    return out / "ncplot"
