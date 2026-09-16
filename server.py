#!/usr/bin/env python3
"""Run skill-launcher straight from a checkout: `python server.py`.

The implementation lives in skill_launcher/cli.py so that the same entry
point works when the package is installed (`skill-launcher` on PATH).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from skill_launcher.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
