#!/usr/bin/env python3
"""Validate runtime configuration without opening the database or Plaid."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from worthit.config import ConfigurationError, PLAID_ENV, validate_runtime_config


def main() -> int:
    try:
        validate_runtime_config()
    except ConfigurationError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"WorthIt configuration valid ({PLAID_ENV}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
