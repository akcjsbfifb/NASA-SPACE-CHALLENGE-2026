"""Offline entry: lunar_data from backend/processing (or pip install --no-deps -e backend)."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO / "backend" / "processing") not in sys.path:
    sys.path.insert(0, str(_REPO / "backend" / "processing"))

from lunar_data.__main__ import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())