#!/usr/bin/env python3
"""Unified CLI for MyFitnessPal data management.

Usage:
    python cli.py mfp fetch --today
    python cli.py mfp parse --merge
    python cli.py mfp sync --dry-run

    python cli.py polar fetch --since-last-entry
    python cli.py polar parse --merge

Or use packages directly:
    python -m backend.mfp fetch --today
    python -m backend.polar fetch --since-last-entry
"""

import sys
import subprocess


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    service = sys.argv[1]
    command = sys.argv[2] if len(sys.argv) > 2 else None
    args = sys.argv[3:] if len(sys.argv) > 3 else []

    if service == "mfp":
        if command in ["fetch", "parse", "sync"]:
            cmd = [sys.executable, "-m", f"backend.mfp.{command}"] + args
            subprocess.run(cmd)
        else:
            print(f"Unknown MFP command: {command}")
            print("Available: fetch, parse, sync")
            sys.exit(1)

    elif service == "polar":
        if command in ["fetch", "parse"]:
            cmd = [sys.executable, "-m", f"backend.polar.{command}"] + args
            subprocess.run(cmd)
        else:
            print(f"Unknown Polar command: {command}")
            print("Available: fetch, parse")
            sys.exit(1)

    else:
        print(f"Unknown service: {service}")
        print("Available services: mfp, polar")
        sys.exit(1)


if __name__ == "__main__":
    main()
