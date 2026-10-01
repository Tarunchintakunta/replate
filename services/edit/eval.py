"""Accuracy benchmark for edit.py.

Draws known words in a known font, asks edit.py to replace them, and compares the result
with the same scene drawn with the new words. Nothing here is a real photo: the truth
is only knowable when we drew the picture ourselves.

    services/ocr/.venv/bin/python services/edit/eval.py            # every font installed
    services/ocr/.venv/bin/python services/edit/eval.py --held-out # hide the true font

Scores per case:
  overlap  soft IoU of the new glyphs against the truth (position, size, face, weight)
  family   the chosen face is the family the words were drawn in
  color    largest channel error of the text color, 0..255
  residue  mean pixel error where the truth is plain background (leftover old glyphs)

Exits 1 when mean overlap drops under the floor, so it can gate a change.
"""
import io
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import edit

FLOOR = 0.5  # mean overlap the editor must keep with every font installed
HELD_OUT_FLOOR = 0.4  # and when the true family is hidden from it

FAMILIES = [
    "Helvetica Neue", "Helvetica", "Arial", "Times New Roman", "Georgia", "Courier New",
    "Menlo", "Avenir Next", "Futura", "Impact", "Verdana", "Gill Sans", "Optima",
    "Palatino", "Baskerville", "Didot", "American Typewriter", "Trebuchet MS",
    "Arial Black", "Arial Narrow", "DejaVu Sans", "DejaVu Serif", "Liberation Sans",
]  # fmt: skip
STYLES = ["Regular", "Bold", "Italic", "Medium"]
WORDS = [
    ("Summer Sale", "Winter Deals"),
    ("OPEN 24 HOURS", "CLOSED TODAY"),
    ("what is your problem", "how was your day"),
    ("Total: $1,249.00", "Total: $980.50"),
    ("Grand Opening", "Coming Soon"),
]
SIZES = [18, 28, 44, 72]
# (name, text color, background painter)
SCENES = [
    ("light", (28, 25, 21), lambda w, h, rng: np.full((h, w, 3), (243, 239, 230), np.float32)),
    ("dark", (240, 240, 240), lambda w, h, rng: np.full((h, w, 3), (30, 34, 38), np.float32)),
    ("color", (255, 255, 255), lambda w, h, rng: np.full((h, w, 3), (14, 107, 82), np.float32)),
    ("gradient", (20, 20, 60), lambda w, h, rng: gradient(w, h)),
    ("texture", (250, 245, 220), lambda w, h, rng: texture(w, h, rng)),
]


def gradient(w, h):
    t = np.linspace(0, 1, w, dtype=np.float32)[None, :, None]
    return np.broadcast_to((1 - t) * np.float32([250, 214, 165]) + t * np.float32([255, 153, 153]), (h, w, 3)).copy()


def texture(w, h, rng):
    """Blurred noise: a stand-in for a photo, dark enough for light text."""
    noise = rng.integers(0, 255, (h // 8 + 1, w // 8 + 1, 3)).astype(np.uint8)
    big = Image.fromarray(noise).resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(3))
    return np.asarray(big, np.float32) * 0.45 + 20


def draw(bg, face, size, text, color, origin):
    """The scene plus `text`: drawn at 2x and scaled down, then through JPEG, so the
    glyph edges are not the ones edit.py will produce. Returns (image, coverage)."""
    h, w = bg.shape[:2]
    layer = Image.new("L", (w * 2, h * 2), 0)
    ImageDraw.Draw(layer).text(
        (origin[0] * 2, origin[1] * 2), text, font=edit.load(face, size * 2), fill=255, anchor="ls"
    )
    alpha = np.asarray(layer.resize((w, h), Image.LANCZOS), np.float32)[:, :, None] / 255
    img = np.clip(bg * (1 - alpha) + np.float32(color) * alpha, 0, 255).astype(np.uint8)
    jpeg = io.BytesIO()
    Image.fromarray(img).save(jpeg, format="JPEG", quality=88)
    return np.array(Image.open(jpeg).convert("RGB")), alpha[:, :, 0]


def family_of(face):
    return edit.load(face, 20).getname()[0]


def cases(faces):
    by_name = {}
    for face in faces:
        if face[2] is None:
            by_name.setdefault(edit.load(face, 20).getname(), face)
    picked = [
        (family, style, by_name[(family, style)])
        for family in FAMILIES
        for style in STYLES
        if (family, style) in by_name
    ]
    n = 0
    for family, style, face in picked:
        for si, (scene, color, paint) in enumerate(SCENES):
            # Every face meets every scene; sizes and words rotate so the run stays short.
            size = SIZES[(n + si) % len(SIZES)]
            old, new = WORDS[(n + si) % len(WORDS)]
            yield family, style, face, scene, color, paint, size, old, new
        n += 1


def main():
    held_out = "--held-out" in sys.argv
    rng = np.random.default_rng(7)
    faces = edit.installed_faces()
    families = {face: family_of(face) for face in faces}
    rows = []
    for family, style, face, scene, color, paint, size, old, new in cases(faces):
        w, h = 1100, size * 3
        origin = (40, size * 2)
        bg = paint(w, h, rng)
        before, old_alpha = draw(bg, face, size, old, color, origin)
        truth, new_alpha = draw(bg, face, size, new, color, origin)

        ys, xs = np.nonzero(old_alpha > 0.5)
        pad = 3  # OCR boxes are a little loose
        box = {
            "from": old,
            "to": new,
            "x": int(xs.min()) - pad,
            "y": int(ys.min()) - pad,
            "width": int(xs.max() - xs.min()) + 2 * pad,
            "height": int(ys.max() - ys.min()) + 2 * pad,
        }
        pool = [f for f in faces if families[f] != family] if held_out else faces
        out = before.copy()
        info = edit.replace(out, box, pool) or {}

        # Coverage of whatever was drawn, measured the way the truth was built.
        plain = np.asarray(Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8)), np.float32)
        axis = np.float32(color) - plain
        got = np.clip(((out - plain) * axis).sum(2) / np.maximum((axis * axis).sum(2), 1), 0, 1)
        union = np.maximum(got, new_alpha).sum()
        overlap = float(np.minimum(got, new_alpha).sum() / union) if union else 0.0
        clear = new_alpha < 0.02
        residue = float(np.abs(out.astype(np.float32) - truth)[clear].mean())
        color_err = float(np.abs(np.float32(info.get("color", (0, 0, 0))) - np.float32(color)).max())
        chosen = families.get(info.get("face"), "?")
        rows.append((scene, family, style, size, overlap, chosen == family, color_err, residue, chosen))

    if "-v" in sys.argv:
        for r in rows:
            print("%-9s %-20s %-8s %3d  overlap %.2f  %s  color %3.0f  residue %4.1f  -> %s" % (
                r[0], r[1], r[2], r[3], r[4], "ok " if r[5] else "MISS", r[6], r[7], r[8]))

    def mean(i, subset=rows):
        return float(np.mean([r[i] for r in subset])) if subset else 0.0

    print(f"\n{len(rows)} cases, true font {'hidden' if held_out else 'installed'}")
    for scene, *_ in SCENES:
        subset = [r for r in rows if r[0] == scene]
        print("  %-9s overlap %.2f  family %3.0f%%  residue %4.1f" % (
            scene, mean(4, subset), 100 * mean(5, subset), mean(7, subset)))
    passed = float(np.mean([r[4] >= 0.5 for r in rows]))
    print("  overall   overlap %.2f  family %3.0f%%  color error %.0f  cases over 0.5: %.0f%%" % (
        mean(4), 100 * mean(5), mean(6), 100 * passed))

    floor = HELD_OUT_FLOOR if held_out else FLOOR
    if mean(4) < floor:
        print(f"FAIL: mean overlap {mean(4):.2f} is under {floor}")
        sys.exit(1)


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    main()
