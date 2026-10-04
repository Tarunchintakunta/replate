#!/usr/bin/env python3
"""Run real edits on photos and record print measurements, not a match percent.

    python scripts/eval_edits.py cases.json out_dir/

cases.json: [{"image": "test-images/x.jpg", "ocr": "x.json", "line": "OLD", "new": "NEW", "mode": "auto"}]
The OCR file is the cached detector output ([{"text", "conf", "poly"}]), so the
edit path runs without reloading Paddle. For each case this writes the edited
image, a before/after strip (3x), and one row of measurements in report.md:
stroke width, ink colour distance (Lab), edge energy ratio, outline before/after,
pixel change on unchanged characters, and new-letter aspect vs page glyphs.
"""

from __future__ import annotations

import json
import sys
from difflib import SequenceMatcher
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.errors import AppError  # noqa: E402
from app.image.editing import _page_bank, replace_raster_text  # noqa: E402
from app.image.masking import build_text_mask  # noqa: E402
from app.image.style import estimate_style  # noqa: E402
from app.ocr.base import RawDetection  # noqa: E402
from app.ocr.normalize import normalize_detections  # noqa: E402
from app.rendering import print_style  # noqa: E402
from app.rendering.glyph_bank import segment_columns  # noqa: E402


def regions_for(image: np.ndarray, ocr: list[dict]) -> list:
    raw = [RawDetection(text=d["text"], confidence=d["conf"], polygon=d["poly"]) for d in ocr]
    found = normalize_detections(raw, page=0, page_width=float(image.shape[1]))
    for region in found:
        polygon = np.asarray(region.polygon, np.float32)
        _mask, tight = build_text_mask(image, polygon)
        region.style = estimate_style(image, polygon, tight, text=region.text, page_width=float(image.shape[1]), base=region.style)
        region.source_text = region.source_text or region.text
    return found


def measure(before: np.ndarray, after: np.ndarray, polygon: np.ndarray, source: str, new: str, bank) -> dict:
    frame_b = print_style._frame(before, polygon)
    if frame_b is None:
        return {"note": "line could not be framed"}
    ref, ink, shape, warp = frame_b
    out = print_style._warp_like(after, warp, ref.shape)
    spans = segment_columns(ink, source)
    ink_after = print_style._binarize(out, shape)
    row = {}
    if spans is None or ink_after is None:
        return {"note": "no letter cuts"}
    ops = SequenceMatcher(a=source, b=new, autojunk=False).get_opcodes()
    changed = [i for tag, i1, i2, _j1, _j2 in ops if tag != "equal" for i in range(i1, i2)]
    kept = [(i1, i2) for tag, i1, i2, _j1, _j2 in ops if tag == "equal"]
    if kept and kept[0][0] == 0 and changed:
        a, b = spans[0][0], spans[kept[0][1] - 1][1]
        row["prefix_mad"] = round(float(np.abs(out[:, a:b].astype(np.int16) - ref[:, a:b]).mean()), 2)
    lo = spans[min(changed)][0] if changed else spans[0][0]
    hi = spans[max(changed)][1] if changed else spans[-1][1]
    new_lo = lo
    new_cols = np.flatnonzero(ink_after[:, new_lo:].any(axis=0))
    new_hi = new_lo + int(new_cols[-1]) + 1 if new_cols.size else hi
    b_ink, a_ink = ink[:, lo:hi], ink_after[:, new_lo:new_hi]
    row["stroke_before"] = round(print_style._stroke_width(b_ink.astype(np.float32)), 2)
    row["stroke_after"] = round(print_style._stroke_width(a_ink.astype(np.float32)), 2)
    lab_b = cv2.cvtColor(ref[:, lo:hi], cv2.COLOR_BGR2LAB).astype(np.float32)
    lab_a = cv2.cvtColor(out[:, new_lo:new_hi], cv2.COLOR_BGR2LAB).astype(np.float32)
    if b_ink.any() and a_ink.any():
        row["ink_dE"] = round(float(np.linalg.norm(np.median(lab_b[b_ink], 0) - np.median(lab_a[a_ink], 0))), 1)
    gb = cv2.cvtColor(ref[:, lo:hi], cv2.COLOR_BGR2GRAY).astype(np.float32)
    ga = cv2.cvtColor(out[:, new_lo:new_hi], cv2.COLOR_BGR2GRAY).astype(np.float32)
    eb = print_style._otsu_energy(gb)
    row["edge_ratio"] = round(print_style._otsu_energy(ga) / eb, 2) if eb else None
    _p, ink_bgr = print_style.line_colors(ref, ink)
    row["outline_before"] = print_style._outline(ref, ink, ink_bgr)[0] is not None
    _p2, ink_bgr2 = print_style.line_colors(out, ink_after)
    row["outline_after"] = print_style._outline(out, ink_after, ink_bgr2)[0] is not None
    # New letters: width/height of each connected piece vs the page glyph it came from.
    introduced = [c for tag, _i1, _i2, j1, j2 in ops if tag in ("replace", "insert") for c in new[j1:j2] if not c.isspace()]
    count, _labels, stats, _c = cv2.connectedComponentsWithStats(a_ink.astype(np.uint8))
    pieces = sorted((s for s in stats[1:] if s[3] >= 0.45 * a_ink.shape[0] * 0.5), key=lambda s: s[0])
    ratios = []
    for char, s in zip(introduced, pieces):
        if char in bank.samples:
            sample = bank.samples[char][0].rgba
            ratios.append(round((s[2] / s[3]) / (sample.shape[1] / sample.shape[0]), 2))
    if ratios and len(pieces) == len(introduced):
        row["aspect_vs_glyph"] = ratios
    return row


def outside_changes(before: np.ndarray, after: np.ndarray, polygon: np.ndarray) -> int:
    """Pixels that changed outside the edited line (grown by one line height for longer words)."""
    xs, ys = polygon[:, 0], polygon[:, 1]
    h = ys.max() - ys.min()
    keep = np.ones(before.shape[:2], bool)
    x0, x1 = int(max(0, xs.min() - 2 * h)), int(min(before.shape[1], xs.max() + 2 * h))
    y0, y1 = int(max(0, ys.min() - 0.5 * h)), int(min(before.shape[0], ys.max() + 0.5 * h))
    keep[y0:y1, x0:x1] = False
    diff = np.abs(before.astype(np.int16) - after.astype(np.int16)).max(axis=2) > 3
    return int((diff & keep).sum())


def strip(before: np.ndarray, after: np.ndarray, polygon: np.ndarray) -> np.ndarray:
    xs, ys = polygon[:, 0], polygon[:, 1]
    h = ys.max() - ys.min()
    x0, x1 = int(max(0, xs.min() - 1.5 * h)), int(min(before.shape[1], xs.max() + 1.5 * h))
    y0, y1 = int(max(0, ys.min() - 0.6 * h)), int(min(before.shape[0], ys.max() + 0.6 * h))
    pair = np.vstack([before[y0:y1, x0:x1], np.full((4, x1 - x0, 3), 255, np.uint8), after[y0:y1, x0:x1]])
    scale = max(1.0, min(4.0, 900 / max(1, x1 - x0)))
    return cv2.resize(pair, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)


def main() -> int:
    cases = json.loads(Path(sys.argv[1]).read_text())
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = ["| case | engine | draw | note | measurements |", "|---|---|---|---|---|"]
    for index, case in enumerate(cases):
        image = cv2.imread(str(ROOT / case["image"]))
        ocr = json.loads(Path(case["ocr"]).read_text())
        ocr = next(iter(ocr.values())) if isinstance(ocr, dict) else ocr
        regions = regions_for(image, ocr)
        region = next((r for r in regions if r.text == case["line"]), None)
        name = f"{index:02d}_{Path(case['image']).stem}"
        label = f"{case['line']} → {case['new']}"
        if region is None:
            lines.append(f"| {name}: {label} | - | - | line not found by OCR | |")
            continue
        try:
            edited, mode, note, draw, _score = replace_raster_text(image, image, region, case["new"], case.get("mode", "auto"), regions)
        except AppError as exc:
            lines.append(f"| {name}: {label} | - | refused | {exc.code}: {exc.message} | |")
            continue
        polygon = np.asarray(region.polygon, np.float32)
        cv2.imwrite(str(out_dir / f"{name}.png"), edited)
        cv2.imwrite(str(out_dir / f"{name}_strip.png"), strip(image, edited, polygon))
        bank = _page_bank(image, regions)
        row = measure(image, edited, polygon, region.source_text or region.text, case["new"], bank)
        row["outside_changed_px"] = outside_changes(image, edited, polygon)
        lines.append(f"| {name}: {label} | {mode} | {draw} | {note or ''} | {json.dumps(row)} |")
        print(name, label, mode, draw, row, flush=True)
    (out_dir / "report.md").write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
