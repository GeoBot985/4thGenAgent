#!/usr/bin/env python
"""
Developer quick tests.
Runs a lightweight profile of pytest that excludes slow, release, integration, and live tests.
"""

import sys
import subprocess

def main():
    print("Running TaskFrame developer quick tests...")
    print("Profile: not slow and not release and not integration and not live")
    print('Command: python -m pytest tests -m "not slow and not release and not integration and not live" -q')
    print("")

    result = subprocess.run([
        sys.executable,
        "-m",
        "pytest",
        "tests",
        "-m",
        "not slow and not release and not integration and not live",
        "-q"
    ])
    
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
