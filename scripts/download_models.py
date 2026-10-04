#!/usr/bin/env python3
"""Download local model files and warm the PaddleOCR cache.

Run from the repository root:

    python scripts/download_models.py

LaMa weights land in models/lama/big-lama.pt.
PaddleOCR weights land in models/paddlex/official_models/.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
LAMA_REL = "lama/big-lama.pt"
LAMA_URL = "https://github.com/enesmsahin/simple-lama-inpainting/releases/download/v0.1.0/big-lama.pt"
CHECKSUMS = MODELS / "checksums.json"


def main() -> int:
    MODELS.mkdir(parents=True, exist_ok=True)
    expected = _expected_hash()
    target = MODELS / LAMA_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and _sha256(target) == expected:
        print(f"LaMa already present and checksum matches: {target}")
    else:
        print(f"Downloading LaMa ({LAMA_URL})")
        print(f"Destination: {target}")
        _download(LAMA_URL, target)
        digest = _sha256(target)
        if digest != expected:
            target.unlink(missing_ok=True)
            print(f"Checksum mismatch.\n  expected {expected}\n  actual   {digest}", file=sys.stderr)
            return 1
        print(f"LaMa checksum ok: {digest}")

    if "--lama-only" in sys.argv:
        print("Skipping Paddle warmup.")
        return 0

    cache = MODELS / "paddlex"
    os.environ["PADDLE_PDX_CACHE_HOME"] = str(cache)
    os.environ["PADDLEX_HOME"] = str(cache)
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
    os.environ["FLAGS_use_mkldnn"] = "0"
    sys.path.insert(0, str(ROOT / "backend"))
    print(f"Warming PaddleOCR. Weights will be stored under {cache / 'official_models'}")
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (640, 180), "white")
    font = ImageFont.truetype(str(ROOT / "fonts" / "LiberationSans-Regular.ttf"), 42)
    ImageDraw.Draw(image).text((24, 60), "Model warmup", font=font, fill=(0, 0, 0))
    warmup = ROOT / "storage" / "_warmup.png"
    warmup.parent.mkdir(parents=True, exist_ok=True)
    image.save(warmup)
    import numpy as np
    from app.ocr.paddle_provider import PaddleOCRProvider

    detections = PaddleOCRProvider().detect(np.array(image)[:, :, ::-1].copy())
    print("OCR warmup saw:", [item.text for item in detections] or "(no text)")
    print("Done.")
    print(f"  LaMa:    {target}")
    print(f"  Paddle:  {cache / 'official_models'}")
    return 0


def _expected_hash() -> str:
    data = json.loads(CHECKSUMS.read_text(encoding="utf-8"))
    value = data.get(LAMA_REL)
    if not value:
        raise SystemExit(f"{CHECKSUMS} does not list {LAMA_REL}")
    return str(value)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, dest: Path) -> None:
    temporary = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as response, temporary.open("wb") as handle:
        total = int(response.headers.get("Content-Length") or 0)
        read = 0
        while True:
            chunk = response.read(1024 * 256)
            if not chunk:
                break
            handle.write(chunk)
            read += len(chunk)
            if total:
                print(f"  {read / 1_048_576:.1f} / {total / 1_048_576:.1f} MB", end="\r")
    print()
    temporary.replace(dest)


if __name__ == "__main__":
    raise SystemExit(main())
