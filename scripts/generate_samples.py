#!/usr/bin/env python3
"""Write sample images and PDFs for manual testing.

    python scripts/generate_samples.py

Files are written to tests/fixtures/generated/ and are not required by pytest.
The test suite builds its own documents from tests/samples.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.samples import image_bytes, mixed_pdf, native_pdf, scanned_pdf, textured_image  # noqa: E402


def main() -> None:
    dest = ROOT / "tests" / "fixtures" / "generated"
    dest.mkdir(parents=True, exist_ok=True)
    files = {
        "welcome.jpg": image_bytes([("Welcome to Paris", (20, 30, 80), 64)], kind="jpg"),
        "colors.png": image_bytes(
            [("Red fox", (180, 20, 20), 54), ("Blue bird", (20, 40, 170), 54)],
            size=(1000, 360),
        ),
        "texture.png": textured_image(),
        "notes.pdf": native_pdf(
            [
                [("Page one stays", "helv", 22)],
                [("Welcome to Paris", "helv", 26)],
                [("Budget total", "helv", 22)],
            ]
        ),
        "scan.pdf": scanned_pdf(["Only on page one", "Secret on page two", "Marker on page three"]),
        "mixed.pdf": mixed_pdf(),
    }
    for name, payload in files.items():
        path = dest / name
        path.write_bytes(payload)
        print(path)


if __name__ == "__main__":
    main()
