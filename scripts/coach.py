#!/usr/bin/env python3
"""Rainbow coach automation. Run from anywhere: python3 scripts/coach.py --help"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rainbow.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
