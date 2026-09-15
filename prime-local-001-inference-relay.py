#!/usr/bin/env python3
"""Expose a TCP listener inside bwrap and relay it to the host Unix proxy."""

from __future__ import annotations

import os
import selectors
import socket
import subprocess
import sys


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit("relay requires the command to exec")
    socket_path = os.environ["ATLAS_PRIME_INFERENCE_PROXY_SOCKET"]
    port = int(os.environ["ATLAS_PRIME_INFERENCE_PROXY_PORT"])
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", port))
    listener.listen(8)
    listener.setblocking(False)
    selector = selectors.DefaultSelector()
    selector.register(listener, selectors.EVENT_READ)

    # Keep the relay in this namespace while Prime owns the actual process.
    import threading

    def serve() -> None:
        while True:
            for key, _ in selector.select():
                client, _ = key.fileobj.accept()
                try:
                    upstream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    upstream.connect(socket_path)
                except OSError:
                    client.close()
                    continue
                threading.Thread(
                    target=_copy_bidirectional,
                    args=(client, upstream),
                    daemon=True,
                ).start()

    threading.Thread(target=serve, daemon=True).start()
    process = subprocess.Popen(sys.argv[1:])
    try:
        return process.wait()
    finally:
        selector.close()
        listener.close()
        if process.poll() is None:
            process.terminate()


def _copy_bidirectional(left: socket.socket, right: socket.socket) -> None:
    with left, right:
        selector = selectors.DefaultSelector()
        selector.register(left, selectors.EVENT_READ, right)
        selector.register(right, selectors.EVENT_READ, left)
        while selector.get_map():
            for key, _ in selector.select():
                data = key.fileobj.recv(65536)
                if not data:
                    selector.unregister(key.fileobj)
                    key.fileobj.shutdown(socket.SHUT_WR)
                    continue
                key.data.sendall(data)


if __name__ == "__main__":
    raise SystemExit(main())
