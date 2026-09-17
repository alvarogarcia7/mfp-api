"""MyFitnessPal data acquisition and syncing package.

Modules:
- fetch: Download raw food data from MyFitnessPal API
- parse: Process raw food data into local database
- sync: Sync local food entries back to MyFitnessPal
"""

from . import fetch, parse, sync

__all__ = ["fetch", "parse", "sync"]


def cli():
    """CLI entry point for MFP commands."""
    import sys
    if len(sys.argv) > 1:
        cmd = sys.argv.pop(1)
        if cmd == "fetch":
            fetch.main()
        elif cmd == "parse":
            parse.main()
        elif cmd == "sync":
            sync.main()
        else:
            print(f"Unknown command: {cmd}")
            print("Usage: python -m backend.mfp [fetch|parse|sync]")
            sys.exit(1)
    else:
        print("Usage: python -m backend.mfp [fetch|parse|sync]")
        print("  fetch  - Download food data from MyFitnessPal API")
        print("  parse  - Process raw food data into database")
        print("  sync   - Sync local food entries to MyFitnessPal")
        sys.exit(1)


if __name__ == "__main__":
    cli()
