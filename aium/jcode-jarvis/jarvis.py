#!/usr/bin/env python3
"""Jarvis entrypoint: one container, local speech, cloud brain."""
from __future__ import annotations

import argparse
import os

from app.api import serve
from app.core import Core
from app.device import device_loop
from app.supervisor import Supervisor


def main() -> int:
    parser = argparse.ArgumentParser(description="Jarvis voice companion")
    parser.add_argument("--host", default=os.environ.get("JARVIS_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("JARVIS_PORT", "8765")))
    parser.add_argument("--data-dir", default=os.environ.get("JARVIS_DATA", "/data"))
    parser.add_argument("--no-supervise", action="store_true")
    parser.add_argument("--device", action="store_true")
    parser.add_argument("--lang", default="auto", choices=["auto", "en", "fr"])
    args = parser.parse_args()

    core = Core(args)
    supervisor = Supervisor(core, enabled=not args.no_supervise)
    supervisor.start()
    try:
        if args.device:
            device_loop(core, args.lang)
            return 0
        serve(core, args.host, args.port)
    finally:
        supervisor.close()
        core.store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
