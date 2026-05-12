"""Cycle 14 smoke test: the new ssh_broker package imports cleanly."""
import importlib


def test_ssh_broker_package_imports():
    mod = importlib.import_module("src.ssh_broker")
    assert mod is not None
