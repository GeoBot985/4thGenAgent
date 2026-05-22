#!/usr/bin/env python
"""
Developer quick tests.

Compatibility wrapper around the bounded validation runner.
"""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    print("Running TaskFrame developer quick tests...")
    print("Profile: bounded local validation")
    print("Command: python tools/run_bounded_validation.py local")
    print("")
    result = subprocess.run([sys.executable, "tools/run_bounded_validation.py", "local"], cwd=str(ROOT))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
