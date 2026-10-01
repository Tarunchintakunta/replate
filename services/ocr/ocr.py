import json
import sys

import cv2
from rapidocr_onnxruntime import RapidOCR

# Display type is cut up at full size ("ummer" for "Summer"), so the image is read a
# second time at this scale, and only lines this tall may be corrected from it.
COARSE = 0.35
DISPLAY_HEIGHT = 48
MIN_CONFIDENCE = 0.7  # for a line only the coarse pass saw


def read(engine, image, scale):
    """Lines of one OCR pass, with boxes in full-size image pixels."""
    height, width = image.shape[:2]
    if scale != 1:
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    result, _ = engine(image)

    lines = []
    for box, text, conf in result or []:
        xs = [pt[0] / scale for pt in box]
        ys = [pt[1] / scale for pt in box]
        x, y = max(int(min(xs)), 0), max(int(min(ys)), 0)
        w, h = min(int(max(xs)), width) - x, min(int(max(ys)), height) - y
        if w <= 0 or h <= 0:
            continue
        lines.append({"text": text, "confidence": float(conf), "x": x, "y": y, "width": w, "height": h})
    return lines


def holds(outer, inner):
    """True when the center of `inner` lies in `outer`."""
    cx, cy = inner["x"] + inner["width"] / 2, inner["y"] + inner["height"] / 2
    return outer["x"] <= cx <= outer["x"] + outer["width"] and outer["y"] <= cy <= outer["y"] + outer["height"]


def merge(fine, coarse):
    """The full-size reading, corrected where the coarse pass saw clearly more.

    Full size reads small text best, so it wins by default. A coarse line replaces a
    fine one only when it is the same display-size line but distinctly wider (the fine
    box lost a glyph), and is added when the fine pass missed it altogether.
    """
    lines = list(fine)
    for c in coarse:
        if c["confidence"] < MIN_CONFIDENCE:
            continue
        inside = [f for f in lines if holds(c, f)]
        if not inside:
            if not any(holds(f, c) for f in lines):
                lines.append(c)
        elif (
            len(inside) == 1
            and inside[0]["height"] >= DISPLAY_HEIGHT
            and c["width"] > 1.15 * inside[0]["width"]
        ):
            lines[lines.index(inside[0])] = c
    return sorted(lines, key=lambda l: (l["y"], l["x"]))


def join_words(lines):
    """Display type comes back one word per box. Neighbors on one baseline become one
    line, so a headline is replaced as a whole. Small text is left alone: there a close
    neighbor is another element (a timestamp beside a message)."""
    lines = sorted(lines, key=lambda l: l["x"])
    merged = True
    while merged:
        merged = False
        for a in lines:
            for b in lines:
                if a is b or b["x"] < a["x"]:
                    continue
                tall = min(a["height"], b["height"])
                shared = min(a["y"] + a["height"], b["y"] + b["height"]) - max(a["y"], b["y"])
                gap = b["x"] - (a["x"] + a["width"])
                if tall < DISPLAY_HEIGHT or shared < 0.6 * tall or not -0.2 * tall <= gap <= 0.8 * tall:
                    continue
                top, bottom = min(a["y"], b["y"]), max(a["y"] + a["height"], b["y"] + b["height"])
                a.update(
                    text=f'{a["text"]} {b["text"]}',
                    confidence=min(a["confidence"], b["confidence"]),
                    width=b["x"] + b["width"] - a["x"],
                    y=top,
                    height=bottom - top,
                )
                lines.remove(b)
                merged = True
                break
            if merged:
                break
    return sorted(lines, key=lambda l: (l["y"], l["x"]))


def main():
    if len(sys.argv) < 2:
        print("Usage: ocr.py <image_path>", file=sys.stderr)
        sys.exit(1)

    try:
        image = cv2.imread(sys.argv[1])
        if image is None:
            raise ValueError("not an image")
        engine = RapidOCR()
        lines = read(engine, image, 1)
        if max(image.shape[:2]) >= 600:
            lines = merge(lines, read(engine, image, COARSE))
        lines = join_words(lines)
    except Exception as e:
        print(f"Error running OCR: {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps({"lines": lines}))


if __name__ == "__main__":
    main()
