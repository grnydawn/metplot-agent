# tests/mcp/netcdf_reader/integration/conftest.py
"""Integration-tier conftest. Loads optional .env.test from repo root."""
from __future__ import annotations

import os
from pathlib import Path

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: pinned-real-files")
    config.addinivalue_line("markers", "real_ssh: real SSH endpoint")


@pytest.fixture(autouse=True, scope="session")
def _load_env_test():
    p = Path(__file__).resolve().parents[4] / ".env.test"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)
