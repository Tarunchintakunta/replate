import json
import sys

import cv2
from rapidocr_onnxruntime import RapidOCR

# The detector's default enlarges an image until its short side is 736px. That suits
# body text and wrecks display type: a headline comes back in pieces with letters
# missing ("ummer", "Fe", "estival"). A second detection with the long side capped here
# sees a headline at a size it can hold, as one line.
COARSE_LONG_SIDE = 480
DISPLAY_HEIGHT = 48  # px; only lines this tall are taken from the coarse pass
MIN_CONFIDENCE = 0.7  # for a line only the coarse pass saw


def read(engine, image):
    """Lines of one OCR pass, with boxes clipped to the image."""
    height, width = image.shape[:2]
    result, _ = engine(image)

    lines = []
    for box, text, conf in result or []:
        xs = [pt[0] for pt in box]
        ys = [pt[1] for pt in box]
        x, y = max(int(min(xs)), 0), max(int(min(ys)), 0)
        w, h = min(int(max(xs)), width) - x, min(int(max(ys)), height) - y
        if w <= 0 or h <= 0 or not text.strip():
            continue
        lines.append({"text": text.strip(), "confidence": float(conf), "x": x, "y": y, "width": w, "height": h})
    return lines


def holds(outer, inner):
    """True when the center of `inner` lies in `outer`."""
    cx, cy = inner["x"] + inner["width"] / 2, inner["y"] + inner["height"] / 2
    return outer["x"] <= cx <= outer["x"] + outer["width"] and outer["y"] <= cy <= outer["y"] + outer["height"]


def merge(fine, coarse):
    """Body text from the fine pass, display type from the coarse pass.

    A coarse line replaces the fine lines inside it only when it is display-size and
    they are pieces of that same line (about as tall as it is). Two rows of small text
    that the coarse pass ran together stay as the fine pass read them. A coarse line
    with no fine line near it was missed by the fine pass and is added.
    """
    lines = list(fine)
    for c in coarse:
        if c["confidence"] < MIN_CONFIDENCE:
            continue
        inside = [f for f in lines if holds(c, f)]
        if not inside:
            if not any(holds(f, c) for f in lines):
                lines.append(c)
        elif c["height"] >= DISPLAY_HEIGHT and all(f["height"] >= 0.6 * c["height"] for f in inside):
            lines = [f for f in lines if not any(f is i for i in inside)]
            lines.append(c)
    return sorted(lines, key=lambda l: (l["y"], l["x"]))


def main():
    if len(sys.argv) < 2:
        print("Usage: ocr.py <image_path>", file=sys.stderr)
        sys.exit(1)

    try:
        image = cv2.imread(sys.argv[1])
        if image is None:
            raise ValueError("not an image")
        fine = read(RapidOCR(), image)
        # det_model_path=None keeps the bundled model; the library wants the key present.
        coarse_engine = RapidOCR(det_model_path=None, det_limit_side_len=COARSE_LONG_SIDE, det_limit_type="max")
        lines = merge(fine, read(coarse_engine, image))
    except Exception as e:
        print(f"Error running OCR: {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps({"lines": lines}))


if __name__ == "__main__":
    main()
