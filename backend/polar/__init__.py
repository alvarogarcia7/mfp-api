"""Polar Flow data acquisition and parsing package.

Modules:
- fetch: Download calendar events from Polar Flow API
- parse: Process calendar events into exercise database
"""

from . import fetch, parse

__all__ = ["fetch", "parse"]


def cli():
    """CLI entry point for Polar Flow commands."""
    import sys
    if len(sys.argv) > 1:
        cmd = sys.argv.pop(1)
        if cmd == "fetch":
            fetch.main()
        elif cmd == "parse":
            parse.main()
        else:
            print(f"Unknown command: {cmd}")
            print("Usage: python -m backend.polar [fetch|parse]")
            sys.exit(1)
    else:
        print("Usage: python -m backend.polar [fetch|parse]")
        print("  fetch  - Download calendar events from Polar Flow API")
        print("  parse  - Process calendar events into database")
        sys.exit(1)


if __name__ == "__main__":
    cli()
