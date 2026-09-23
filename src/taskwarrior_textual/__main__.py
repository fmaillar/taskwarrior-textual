"""Command-line entry point."""

from .app import run


def main() -> None:
    """Launch taskwarrior-textual."""
    run()


if __name__ == "__main__":
    main()
