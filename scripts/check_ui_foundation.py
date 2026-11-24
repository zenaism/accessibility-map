# ruff: noqa: E501
"""Measure contrast, target size, names, requests and scroll on the components page. Exit code 1 on any failure.

python scripts/check_ui_foundation.py [--shots DIR]
"""

import argparse
import sys
from pathlib import Path

from atlas import ui_checks

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", type=Path, help="write full-page screenshots here")
    ap.add_argument("--no-axe", action="store_true")
    a = ap.parse_args()
    r = ui_checks.run(a.shots, use_axe=not a.no_axe)
    print(ui_checks.report(r))
    sys.exit(1 if r["failures"] else 0)
