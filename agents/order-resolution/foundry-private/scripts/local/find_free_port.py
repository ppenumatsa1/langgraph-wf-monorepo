from __future__ import annotations

import random
import socket


def main() -> None:
    ports = list(range(20_000, 30_000))
    random.shuffle(ports)

    for port in ports:
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
        print(port)
        return

    raise RuntimeError("No free local port is available in the Docker-safe range.")


if __name__ == "__main__":
    main()
