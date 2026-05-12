"""serve_forever exits within ~1s of idle_timeout expiring."""
from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

from src.ssh_broker.server import serve_forever


def test_server_exits_after_idle_timeout(tmp_path):
    holder = MagicMock()
    holder.is_alive.return_value = True
    sock_path = str(tmp_path / "broker.sock")
    stop = threading.Event()
    t = threading.Thread(
        target=serve_forever,
        kwargs=dict(holder=holder, socket_path=sock_path,
                    stop_event=stop, idle_timeout=0.5,
                    poll_interval=0.1),
        daemon=True,
    )
    started = time.time()
    t.start()
    t.join(timeout=5)
    elapsed = time.time() - started
    assert not t.is_alive(), "server thread should have exited"
    assert elapsed < 4.0
    assert not Path(sock_path).exists()


def test_server_does_not_exit_with_no_idle_timeout(tmp_path):
    """When idle_timeout is None, the server runs forever (until stop)."""
    holder = MagicMock()
    holder.is_alive.return_value = True
    sock_path = str(tmp_path / "broker.sock")
    stop = threading.Event()
    t = threading.Thread(
        target=serve_forever,
        kwargs=dict(holder=holder, socket_path=sock_path,
                    stop_event=stop, idle_timeout=None,
                    poll_interval=0.05),
        daemon=True,
    )
    t.start()
    time.sleep(0.8)
    assert t.is_alive()
    stop.set()
    t.join(timeout=3)
    assert not t.is_alive()
