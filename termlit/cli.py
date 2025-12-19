"""Command line interface for the Termlit toolkit."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List

AUTH_MODES = ("ssh", "none")

from . import __version__
from .runtime import run_local_script, serve_script, serve_script_with_reloader


def _parse_users(raw_entries: List[str]) -> Dict[str, str]:
    users: Dict[str, str] = {}
    for raw in raw_entries:
        if "=" not in raw:
            raise argparse.ArgumentTypeError(
                f"Invalid user definition '{raw}'. Use the form username=password."
            )
        username, password = raw.split("=", 1)
        if not username or not password:
            raise argparse.ArgumentTypeError(
                f"Invalid user definition '{raw}'. Username and password are required."
            )
        users[username] = password
    return users


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="termlit", description="Termlit CLI")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show Termlit version and exit.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run", help="Serve a Termlit script over SSH (default command)"
    )
    run_parser.add_argument("script", help="Path to the Termlit script")
    run_parser.add_argument("--host", default="0.0.0.0", help="SSH host to bind")
    run_parser.add_argument("--port", type=int, default=2222, help="SSH port")
    run_parser.add_argument(
        "--auth",
        choices=AUTH_MODES,
        default="ssh",
        help="Authentication mode: 'ssh' asks for a password (default), "
        "while 'none' allows passwordless sessions.",
    )
    run_parser.add_argument(
        "--user",
        action="append",
        default=[],
        help="Provide login credentials as username=password. Repeatable.",
    )
    run_parser.add_argument(
        "--allow-anonymous",
        action="store_true",
        help="Allow any username/password (disables default accounts).",
    )
    run_parser.add_argument(
        "--reload",
        action="store_true",
        help="Watch the target script and restart the server when it changes.",
    )
    run_parser.add_argument(
        "--local",
        action="store_true",
        help="Run the script locally without starting an SSH server.",
    )

    args = parser.parse_args(argv)

    if args.command == "run":
        script_path = Path(args.script).expanduser().resolve()
        if not script_path.exists():
            parser.error(f"Script not found: {script_path}")

        if args.local:
            run_local_script(script_path)
            return

        if args.auth == "none":
            if args.user:
                parser.error("--user and --auth none are mutually exclusive.")
            if args.allow_anonymous:
                parser.error("--allow-anonymous is not needed with --auth none.")
            selected_users = None
        else:
            users = _parse_users(args.user)
            selected_users = {} if args.allow_anonymous else users or None

        serve_fn = serve_script_with_reloader if args.reload else serve_script
        try:
            serve_fn(
                script_path,
                host=args.host,
                port=args.port,
                users=selected_users,
                auth_mode=args.auth,
            )
        except KeyboardInterrupt:
            print("\n[Termlit] Shutting down.")
            sys.exit(0)
