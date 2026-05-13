"""UNIX-socket server loop for the metplot-ssh-broker.

Single-threaded `selectors` loop. Reads newline-delimited JSON-RPC
requests, dispatches to METHODS, writes the response. Methods
serialize through the SessionHolder mutex inside METHODS — the
server itself is single-threaded so concurrent clients queue.
"""
from __future__ import annotations

import os
import selectors
import socket
import threading
import time
from pathlib import Path
from typing import Any

from src.ssh_broker.methods import METHODS, BrokerError
from src.ssh_broker.protocol import (
    CONNECTION_LOST, INTERNAL_ERROR, INVALID_PARAMS, METHOD_NOT_FOUND,
    PARSE_ERROR, decode_line, encode_message, make_error, make_response,
)


class BrokerSession:
    """Per-client read/write buffers."""

    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self.read_buf = bytearray()
        self.write_buf = bytearray()


def _dispatch_one(holder, line: bytes, *,
                   extra_allowed: set[str] | None = None) -> bytes:
    """Parse one line, dispatch, return one encoded reply."""
    try:
        req = decode_line(line)
    except Exception:
        return encode_message(make_error(0, PARSE_ERROR, "parse error"))
    req_id = req.get("id", 0)
    method = req.get("method", "")
    params = req.get("params") or {}

    if not holder.is_alive():
        return encode_message(make_error(req_id, CONNECTION_LOST,
                                          "connection lost"))

    fn = METHODS.get(method)
    if fn is None:
        return encode_message(make_error(req_id, METHOD_NOT_FOUND,
                                          f"unknown method {method!r}"))
    try:
        result = fn(holder, params, extra_allowed=extra_allowed)
    except KeyError as e:
        return encode_message(make_error(
            req_id, INVALID_PARAMS,
            f"missing param: {e.args[0]!r}"))
    except BrokerError as e:
        return encode_message(make_error(req_id, e.code, e.message))
    except Exception as e:
        return encode_message(make_error(
            req_id, INTERNAL_ERROR,
            f"{type(e).__name__}: {e}"))
    return encode_message(make_response(req_id, result))


def serve_forever(
    *,
    holder: Any,
    socket_path: str,
    stop_event: threading.Event | None = None,
    idle_timeout: float | None = None,
    poll_interval: float = 0.2,
    extra_allowed: set[str] | None = None,
) -> None:
    """Block until stop_event is set or idle_timeout elapses."""
    stop = stop_event or threading.Event()
    p = Path(socket_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        p.unlink()

    server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server_sock.setblocking(False)
    server_sock.bind(socket_path)
    os.chmod(socket_path, 0o600)
    server_sock.listen(8)

    sel = selectors.DefaultSelector()
    sel.register(server_sock, selectors.EVENT_READ, data=None)
    sessions: dict[int, BrokerSession] = {}

    last_activity = time.time()
    # Cycle-14: self-exit on connection loss (spec §1.6).
    # Track when the holder first went dead so we can flush pending
    # write buffers before exiting (one extra poll cycle).
    holder_dead_since: float | None = None

    try:
        while not stop.is_set():
            events = sel.select(timeout=poll_interval)
            for key, mask in events:
                if key.data is None:
                    # Accept
                    try:
                        conn, _ = server_sock.accept()
                    except (BlockingIOError, InterruptedError):
                        continue
                    conn.setblocking(False)
                    sess = BrokerSession(conn)
                    sessions[conn.fileno()] = sess
                    sel.register(conn,
                                  selectors.EVENT_READ | selectors.EVENT_WRITE,
                                  data=sess)
                else:
                    sess: BrokerSession = key.data  # type: ignore[no-redef]
                    if mask & selectors.EVENT_READ:
                        try:
                            chunk = sess.sock.recv(4096)
                        except (BlockingIOError, InterruptedError):
                            continue
                        if not chunk:
                            try:
                                sel.unregister(sess.sock)
                            except KeyError:
                                pass
                            sessions.pop(sess.sock.fileno(), None)
                            sess.sock.close()
                            continue
                        sess.read_buf.extend(chunk)
                        last_activity = time.time()
                        while b"\n" in sess.read_buf:
                            nl = sess.read_buf.index(b"\n")
                            line = bytes(sess.read_buf[:nl + 1])
                            del sess.read_buf[:nl + 1]
                            reply = _dispatch_one(
                                holder, line, extra_allowed=extra_allowed)
                            sess.write_buf.extend(reply)
                    if mask & selectors.EVENT_WRITE and sess.write_buf:
                        try:
                            n = sess.sock.send(sess.write_buf)
                        except (BlockingIOError, InterruptedError):
                            continue
                        del sess.write_buf[:n]
            if idle_timeout is not None:
                if time.time() - last_activity > idle_timeout:
                    break
            # Cycle-14: self-exit on connection loss (spec §1.6).
            # Record when we first noticed the holder was dead, then
            # wait at least one extra poll cycle before exiting so that
            # any in-flight CONNECTION_LOST replies finish flushing.
            if not holder.is_alive():
                if holder_dead_since is None:
                    holder_dead_since = time.time()
                elif time.time() - holder_dead_since > poll_interval:
                    pending = any(s.write_buf for s in sessions.values())
                    if not pending:
                        break
    finally:
        for sess in list(sessions.values()):
            try:
                sel.unregister(sess.sock)
            except (KeyError, ValueError):
                pass
            try:
                sess.sock.close()
            except Exception:
                pass
        try:
            sel.unregister(server_sock)
        except (KeyError, ValueError):
            pass
        try:
            server_sock.close()
        except Exception:
            pass
        try:
            Path(socket_path).unlink()
        except FileNotFoundError:
            pass
        try:
            sel.close()
        except Exception:
            pass
