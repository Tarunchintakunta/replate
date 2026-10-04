#!/usr/bin/env python3
"""Render every font in models/font-library once into models/font-library/index.npz.

    python scripts/build_font_index.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.rendering.font_library import build_index  # noqa: E402

if __name__ == "__main__":
    started = time.time()
    print("Wrote", build_index(), f"in {time.time() - started:.0f}s")
