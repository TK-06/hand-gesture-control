"""The Bluetooth remote: ``python -m gesturectl.hid <command>``.

    serve                      run the service (Raspberry Pi; normally started by systemd)
    send <action>              press a media key on the phone, e.g. send volume_up
    pair                       accept a new phone for a while (default 120 s)
    status                     what's connected and paired

All but ``serve`` talk to a running service, so they work from any SSH session.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from gesturectl.config import ACTIONS, load_config
from gesturectl.logsetup import setup_logging


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m gesturectl.hid", description=__doc__.splitlines()[0])
    parser.add_argument("--config", help="extra settings layered on config/default.yaml, e.g. config/car.yaml")
    sub = parser.add_subparsers(dest="command")
    serve_p = sub.add_parser("serve", help="run the Bluetooth remote service")
    serve_p.add_argument("--log-level", default="INFO")
    serve_p.add_argument("--log-file", help="also write a rotating log file, e.g. logs/hid.log")
    send_p = sub.add_parser("send", help="press a media key on the phone")
    send_p.add_argument("action", choices=ACTIONS)
    sub.add_parser("pair", help="accept a new phone for a while")
    sub.add_parser("status", help="show connection and pairing state")
    args = parser.parse_args(argv)
    cfg = load_config(args.config)

    if args.command in (None, "serve"):
        setup_logging(getattr(args, "log_level", "INFO"), getattr(args, "log_file", None))
        from gesturectl.hid.service import run

        try:
            asyncio.run(run(cfg))
        except KeyboardInterrupt:
            pass
        return 0

    from gesturectl.hid.protocol import request

    command = args.action if args.command == "send" else args.command
    try:
        reply = request(command, cfg.hid.host, cfg.hid.port, timeout=3.0)
    except OSError as exc:
        print(f"the Bluetooth remote service isn't running ({exc})", file=sys.stderr)
        return 2
    print(reply)
    return 0 if not reply.startswith("error") else 1


if __name__ == "__main__":
    sys.exit(main())
