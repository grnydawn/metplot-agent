# tests/targets/_common/conftest.py
"""Ensure the top-level `targets` package is importable.

When pytest adds `tests/` to sys.path, the `tests/targets/` directory can
shadow the top-level `targets/` package.  Insert the repo root at the front
so that `from targets._common.xxx import ...` always resolves to the real
implementation, not to the test namespace.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parents[3])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
