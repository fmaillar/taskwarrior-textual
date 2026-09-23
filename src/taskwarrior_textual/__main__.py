"""Command-line entry point."""

import argparse
import sys
from collections.abc import Sequence

from . import __version__
from .app import run
from .config import ConfigError, default_config_path, load_planning_settings


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="taskwarrior-textual")
    parser.add_argument(
        "--version",
        action="store_true",
        help="print the installed taskwarrior-textual version and exit",
    )
    parser.add_argument(
        "--config-path",
        action="store_true",
        help="print the resolved configuration path and exit",
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="validate the resolved configuration and exit",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Process command-line options, then launch taskwarrior-textual."""
    args = _parser().parse_args(argv)

    if args.version:
        print(f"taskwarrior-textual {__version__}")
        return
    if args.config_path:
        print(default_config_path())
        return

    try:
        if args.check_config:
            load_planning_settings()
            print(f"configuration ok: {default_config_path()}")
            return
        run()
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
