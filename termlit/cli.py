"""Command line interface for the Termlit toolkit."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List

from .runtime import serve_script


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
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run", help="Serve a Termlit script over SSH (default command)"
    )
    run_parser.add_argument("script", help="Path to the Termlit script")
    run_parser.add_argument("--host", default="0.0.0.0", help="SSH host to bind")
    run_parser.add_argument("--port", type=int, default=2222, help="SSH port")
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

    args = parser.parse_args(argv)

    if args.command == "run":
        script_path = Path(args.script).expanduser().resolve()
        if not script_path.exists():
            parser.error(f"Script not found: {script_path}")

        users = _parse_users(args.user)
        selected_users = {} if args.allow_anonymous else users or None

        try:
            serve_script(
                script_path,
                host=args.host,
                port=args.port,
                users=selected_users,
            )
        except KeyboardInterrupt:
            print("\n[Termlit] Shutting down.")
            sys.exit(0)
