"""Command-line entry point."""

import sys

from .app import run
from .config import ConfigError


def main() -> None:
    """Launch taskwarrior-textual."""
    try:
        run()
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
