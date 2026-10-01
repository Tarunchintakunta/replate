"""Local text replacement, no network and no model weights.

For each box: find the old glyphs, erase them with OpenCV inpainting, pick the installed
font whose rendering of the old words overlaps the old glyphs best, and draw the new
words in that font at the same size, color, and baseline.

stdin:  {"image": <base64 PNG>, "replacements": [{"from", "to", "x", "y", "width", "height"}]}
stdout: the edited PNG, same pixel size as the input.

Runs in the OCR venv: cv2, numpy, and Pillow all arrive with rapidocr-onnxruntime.
"""
import base64
import glob
import io
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT_DIRS = [
    "/System/Library/Fonts",
    "/Library/Fonts",
    os.path.expanduser("~/Library/Fonts"),
    "/usr/share/fonts",
    "C:/Windows/Fonts",
]
# Used when there are no old glyphs to match against.
DEFAULT_FACES = [
    ("/System/Library/Fonts/SFNS.ttf", 0, None),
    ("/System/Library/Fonts/Helvetica.ttc", 0, None),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 0, None),
    ("C:/Windows/Fonts/arial.ttf", 0, None),
]
# Named instances of a variable font worth trying. SF alone ships 400 of them.
WEIGHTS = [b"Light", b"Regular", b"Medium", b"Semibold", b"Bold", b"Heavy", b"Black"]
REF = 48  # px size every face is compared at
MIN_CONTRAST = 30  # below this the box holds no text we can see


def load(face, size):
    path, index, variation = face
    if path is None:
        return ImageFont.load_default(size)
    font = ImageFont.truetype(path, size, index=index)
    if variation:
        font.set_variation_by_name(variation)
    return font


def installed_faces():
    """Every installed face as (path, collection index, variable-font instance or None)."""
    faces = []
    for d in FONT_DIRS:
        for path in sorted(glob.glob(os.path.join(d, "**", "*.[ot]t[fc]"), recursive=True)):
            index = 0
            while True:
                try:
                    # An odd size on purpose: a bitmap-only face (color emoji) loads at
                    # its fixed strikes and nowhere else, and it cannot be resized to match.
                    font = ImageFont.truetype(path, 37, index=index)
                except Exception:
                    break
                try:
                    names = [n for n in font.get_variation_names() if n in WEIGHTS]
                except Exception:
                    names = []
                # A leading dot marks a hidden system copy of a family that is also listed.
                if not font.getname()[0].startswith("."):
                    faces.extend((path, index, n) for n in names or [None])
                index += 1
                if not path.lower().endswith("c"):
                    break
    return faces


def raster(font, text, shift=(0.0, 0.0)):
    """Coverage (0..1) of `text`, cropped to its ink, and that ink box as
    (left, top, right, bottom) relative to the left end of the baseline.
    `shift` moves the pen by a fraction of a pixel; the box stays whole pixels."""
    left, top, right, bottom = font.getbbox(text, anchor="ls")
    pad = 4
    w, h = int(right - left) + 2 * pad, int(bottom - top) + 2 * pad
    if w <= 0 or h <= 0 or w * h > 40_000_000:
        return None
    ox, oy = pad - int(left), pad - int(top)
    img = Image.new("L", (w, h), 0)
    ImageDraw.Draw(img).text((ox + shift[0], oy + shift[1]), text, font=font, fill=255, anchor="ls")
    a = np.asarray(img, dtype=np.float32) / 255
    # Half coverage, the same edge find_ink uses on the old glyphs; a hairline face
    # that never reaches it still gets a box.
    ys, xs = np.nonzero(a > 0.5)
    if len(xs) == 0:
        ys, xs = np.nonzero(a > 0.2)
    if len(xs) == 0:
        return None
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    return a[y0:y1, x0:x1], (x0 - ox, y0 - oy, x1 - ox, y1 - oy)


def covers(font, text):
    """True when the font has a glyph for every character (no tofu boxes)."""
    try:
        missing = font.getmask("\U0010ffff")
        tofu = (missing.size, bytes(missing))
        for ch in set(text):
            if ch.isspace():
                continue
            mask = font.getmask(ch)
            if (mask.size, bytes(mask)) == tofu:
                return False
        return True
    except Exception:
        return False


def find_ink(img, x, y, w, h):
    """Locate the old glyphs in and just around the box.

    Returns None when the box is flat, else a dict with the text color, the box grown to
    hold whole glyphs, per-pixel glyph coverage for that box, the pixels to erase, and
    the tight ink box in image pixels.
    """
    H, W = img.shape[:2]
    m = max(4, round(h * 0.4))  # how far a clipped glyph may reach past the box
    X0, Y0, X1, Y1 = max(x - m, 0), max(y - m, 0), min(x + w + m, W), min(y + h + m, H)
    region = img[Y0:Y1, X0:X1].astype(np.float32)
    left, top, right, bottom = x - X0, y - Y0, x - X0 + w, y - Y0 + h

    ring = np.zeros(region.shape[:2], bool)
    ring[max(top - 2, 0) : bottom + 2, max(left - 2, 0) : right + 2] = True
    ring[top:bottom, left:right] = False
    if not ring.any():  # the box is the whole image
        ring[[0, -1], :] = True
        ring[:, [0, -1]] = True
    bg = np.median(region[ring], axis=0)

    diff = region - bg
    dist = np.linalg.norm(diff, axis=2)
    inside = dist[top:bottom, left:right]
    if inside.max() < MIN_CONTRAST:
        return None

    # Otsu splits glyph pixels from background; the farthest tenth of them is the
    # solid stroke color, free of anti-aliasing.
    scaled = np.clip(inside, 0, 255).astype(np.uint8)
    threshold, _ = cv2.threshold(scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    glyph = dist > max(threshold, MIN_CONTRAST / 2)
    if not glyph[top:bottom, left:right].any():
        return None

    # OCR boxes clip ascenders and descenders, and a clipped glyph reads as a wider,
    # heavier face. Push each edge out while it still cuts through ink. An edge that is
    # mostly "ink" is not text but the next surface (a bubble border), so stop there.
    def cut(edge):
        return edge.any() and edge.mean() < 0.5

    while top > 0 and cut(glyph[top, left:right]):
        top -= 1
    while bottom < glyph.shape[0] and cut(glyph[bottom - 1, left:right]):
        bottom += 1
    while left > 0 and cut(glyph[top:bottom, left]):
        left -= 1
    while right < glyph.shape[1] and cut(glyph[top:bottom, right - 1]):
        right += 1

    grown = (slice(top, bottom), slice(left, right))
    core = glyph[grown] & (dist[grown] >= np.percentile(dist[grown][glyph[grown]], 90))
    color = np.median(region[grown][core], axis=0)

    # Coverage: how far each pixel sits along the line from background to text color.
    axis = color - bg
    alpha = np.clip((diff[grown] @ axis) / max(float(axis @ axis), 1.0), 0, 1)
    ys, xs = np.nonzero(alpha > 0.5)
    if len(xs) == 0:
        return None
    bx, by = X0 + left, Y0 + top
    return {
        "color": color,
        # A flat surround is repainted exactly; anything else is inpainted.
        "fill": bg if region[ring].std(axis=0).max() < 3 else None,
        "box": (bx, by, right - left, bottom - top),
        "alpha": alpha,
        "erase": dist[grown] > max(12.0, 0.2 * float(np.linalg.norm(axis))),
        "ink": (bx + xs.min(), by + ys.min(), bx + xs.max() + 1, by + ys.max() + 1),
    }


def erase(img, x, y, w, h, mask, fill):
    """Remove `mask` (box-sized bool): paint `fill`, or inpaint from the surroundings."""
    H, W = img.shape[:2]
    grow = max(2, round(h * 0.06))
    if mask.mean() > 0.55:
        # ponytail: a busy background gives no clean glyph mask, so the whole box is
        # inpainted and comes out soft. A generative provider does this case better.
        mask = np.ones_like(mask)
    m = 12 + grow
    X0, Y0, X1, Y1 = max(x - m, 0), max(y - m, 0), min(x + w + m, W), min(y + h + m, H)
    full = np.zeros((Y1 - Y0, X1 - X0), np.uint8)
    full[y - Y0 : y - Y0 + h, x - X0 : x - X0 + w] = mask.astype(np.uint8) * 255
    full = cv2.dilate(full, np.ones((3, 3), np.uint8), iterations=grow)
    crop = np.ascontiguousarray(img[Y0:Y1, X0:X1])
    if fill is None:
        img[Y0:Y1, X0:X1] = cv2.inpaint(crop, full, 3, cv2.INPAINT_TELEA)
    else:
        crop[full > 0] = np.round(fill)
        img[Y0:Y1, X0:X1] = crop


def word_spans(alpha):
    """Column ranges of the words: runs of ink split at gaps wider than a quarter of the height."""
    ink = (alpha.max(axis=0) > 0.3).astype(np.int8)
    edges = np.flatnonzero(np.diff(np.concatenate(([0], ink, [0]))))
    starts, ends = edges[::2], edges[1::2]
    if len(starts) == 0:
        return []
    split = np.flatnonzero(starts[1:] - ends[:-1] >= max(2, round(alpha.shape[0] * 0.26)))
    return list(zip(np.concatenate((starts[:1], starts[1:][split])), np.concatenate((ends[:-1][split], ends[-1:]))))


def overlap(a, b):
    """Soft IoU (0..1) of two coverage maps after stretching `b` onto `a`."""
    b = cv2.resize(b, (a.shape[1], a.shape[0]), interpolation=cv2.INTER_AREA)
    union = np.maximum(a, b).sum()
    return float(np.minimum(a, b).sum() / union) if union else 0.0


def similarity(old, new):
    """How alike two renderings of the same words are, 0..1."""
    # A fixed height keeps tiny text from being all rounding.
    def fixed(a):
        width = max(1, min(round(a.shape[1] * 32 / a.shape[0]), 4096))
        return cv2.resize(a, (width, 32), interpolation=cv2.INTER_AREA if a.shape[0] > 32 else cv2.INTER_LINEAR)

    a, b = fixed(old), fixed(new)
    old_words, new_words = word_spans(a), word_spans(b)
    if len(old_words) != len(new_words) or len(old_words) < 2:
        return overlap(a, b)
    # Word by word, so a long line is not scored on how far its last word has drifted.
    total = sum(e - s for s, e in old_words)
    return sum(
        (e - s) * overlap(a[:, s:e], b[:, ns:ne])
        for (s, e), (ns, ne) in zip(old_words, new_words)
    ) / total


def head(old, text, limit=40):
    """The first few words of a long line and the glyphs that belong to them. A face is
    recognizable from five words; drawing all ninety characters in every face is not free."""
    words, spans = text.split(), word_spans(old)
    if len(text) <= limit or len(words) != len(spans):
        return old, text
    count, keep = 0, len(words)
    for i, word in enumerate(words):
        count += len(word) + 1
        if count >= limit:
            keep = i + 1
            break
    part = old[:, : spans[keep - 1][1]]
    rows = np.flatnonzero(part.max(axis=1) > 0.5)
    if len(rows) == 0:
        return old, text
    return part[rows[0] : rows[-1] + 1], " ".join(words[:keep])


def match_font(old, text, faces):
    """Faces ranked by how well their rendering of `text` matches the old glyphs."""
    old, text = head(old, text)
    old_aspect = old.shape[1] / old.shape[0]
    old_density = float(old.mean())
    ranked = []
    for face in faces:
        try:
            font = load(face, REF)
            # Cheap outline metrics first: most faces are the wrong shape and never get drawn.
            left, top, right, bottom = font.getbbox(text, anchor="ls")
            if bottom <= top or not 0.85 < (right - left) / (bottom - top) / old_aspect < 1.18:
                continue
            drawn = raster(font, text)
        except Exception:
            continue
        if drawn is None:
            continue
        new, _ = drawn
        aspect = new.shape[1] / new.shape[0]
        shape = min(aspect, old_aspect) / max(aspect, old_aspect)
        if shape < 0.8:
            continue
        # Overlap alone favors heavy faces (a bold stroke covers a misplaced thin one),
        # so the amount of ink has to agree too.
        density = float(new.mean())
        weight = min(density, old_density) / max(density, old_density)
        ranked.append((similarity(old, new) * shape * weight, face))
    ranked.sort(key=lambda r: -r[0])
    return ranked


def read_text(img, x, y, w, h):
    """OCR one box. Used for a drawn box, where the client has no old text to send."""
    try:
        from rapidocr_onnxruntime import RapidOCR

        H, W = img.shape[:2]
        m = max(8, h // 2)
        crop = img[max(y - m, 0) : min(y + h + m, H), max(x - m, 0) : min(x + w + m, W)]
        result, _ = RapidOCR()(cv2.cvtColor(crop, cv2.COLOR_RGB2BGR))
        return " ".join(item[1] for item in result or []).strip()
    except Exception:
        return ""


def default_face():
    for face in DEFAULT_FACES:
        if os.path.exists(face[0]):
            return face
    return (None, 0, None)  # Pillow's bundled face


def blend(img, alpha, color, left, top):
    """Paint `color` through `alpha` with its top-left corner at (left, top), clipped."""
    H, W = img.shape[:2]
    h, w = alpha.shape
    x0, y0, x1, y1 = max(left, 0), max(top, 0), min(left + w, W), min(top + h, H)
    if x0 >= x1 or y0 >= y1:
        return
    a = alpha[y0 - top : y1 - top, x0 - left : x1 - left, None]
    region = img[y0:y1, x0:x1].astype(np.float32)
    img[y0:y1, x0:x1] = np.clip(region * (1 - a) + color * a + 0.5, 0, 255).astype(np.uint8)


def draw_at(font, text, pen_x, baseline):
    """`text` with its pen at a sub-pixel position: coverage, and its top-left in whole pixels."""
    px, py = int(np.floor(pen_x)), int(np.floor(baseline))
    drawn = raster(font, text, (pen_x - px, baseline - py))
    if drawn is None:
        return None
    alpha, (left, top, _, _) = drawn
    return alpha, px + left, py + top


def register(old, x, y, font, text, pen_x, baseline):
    """Slide the old words, redrawn, over the old glyphs in half-pixel steps and return
    the pen position that overlaps best. `old` is coverage for the box at (x, y)."""
    best = (-1.0, pen_x, baseline)
    for dy in (-1, -0.5, 0, 0.5, 1):
        for dx in (-1, -0.5, 0, 0.5, 1):
            drawn = draw_at(font, text, pen_x + dx, baseline + dy)
            if drawn is None:
                continue
            alpha, left, top = drawn
            layer = np.zeros_like(old)
            x0, y0 = max(left - x, 0), max(top - y, 0)
            x1, y1 = min(left - x + alpha.shape[1], old.shape[1]), min(top - y + alpha.shape[0], old.shape[0])
            if x0 >= x1 or y0 >= y1:
                continue
            layer[y0:y1, x0:x1] = alpha[y0 - (top - y) : y1 - (top - y), x0 - (left - x) : x1 - (left - x)]
            union = np.maximum(old, layer).sum()
            score = float(np.minimum(old, layer).sum() / union) if union else 0.0
            if score > best[0]:
                best = (score, pen_x + dx, baseline + dy)
    return best[1], best[2]


def replace(img, r, faces):
    """Apply one replacement in place. Returns the face, size, and color it drew with."""
    H, W = img.shape[:2]
    x, y = max(0, min(int(r["x"]), W - 1)), max(0, min(int(r["y"]), H - 1))
    w, h = max(1, min(int(r["width"]), W - x)), max(1, min(int(r["height"]), H - y))
    old_text, new_text = r.get("from", "").strip(), r.get("to", "").strip()

    found = find_ink(img, x, y, w, h)
    if found is None:
        if not new_text:
            return
        # Nothing to erase or match: draw in the box, dark on light or light on dark.
        bg = np.median(img[y : y + h, x : x + w].reshape(-1, 3), axis=0)
        color = np.array([255.0] * 3 if bg.mean() < 128 else [0.0] * 3)
        face = default_face()
        drawn = raster(load(face, REF), new_text)
        if drawn is None:
            return
        size = REF * (h * 0.7) / drawn[0].shape[0]
        alpha = (raster(load(face, size), new_text) or drawn)[0]
        blend(img, alpha, color, x, y + (h - alpha.shape[0]) // 2)
        return {"face": face, "size": size, "color": tuple(color)}

    x, y, w, h = found["box"]
    ix0, iy0, ix1, iy1 = found["ink"]
    old = found["alpha"][iy0 - y : iy1 - y, ix0 - x : ix1 - x]
    if not old_text and new_text:
        old_text = read_text(img, x, y, w, h)

    erase(img, x, y, w, h, found["erase"], found["fill"])
    if not new_text:
        return

    # Known old words calibrate everything: the face that redraws them best, and the size
    # at which that face reproduces their height.
    ranked = match_font(old, old_text, faces) if old_text else []
    face = next((f for _, f in ranked[:40] if covers(load(f, REF), new_text)), None)
    reference = old_text
    if face is None:
        face = next(
            (f for f in [default_face(), *faces] if covers(load(f, REF), new_text)),
            default_face(),
        )
        if not ranked:
            reference = new_text
    ref = raster(load(face, REF), reference) or raster(load(face, REF), new_text)
    if ref is None:
        return
    size = REF * (iy1 - iy0) / ref[0].shape[0]
    sized = raster(load(face, size), reference)
    if sized is None:
        return
    stretch = 1.0
    if reference == old_text:
        stretch = (ix1 - ix0) / sized[0].shape[1]
        if 0.93 < stretch < 1.07:
            # Right face: the line's width measures the size far better than its height,
            # which is only a dozen pixels on small text.
            size *= stretch
            sized = raster(load(face, size), reference) or sized
            stretch = 1.0
        # Wrong face, close enough: keep the height and squeeze the width to fit.
        stretch = float(np.clip(stretch, 0.85, 1.18))
    font = load(face, size)
    drawn = raster(font, new_text)
    if drawn is None:
        return
    alpha, (left, top, _, _) = drawn
    width = max(1, round(alpha.shape[1] * stretch))

    # Left-aligned text keeps its pen position, not its ink edge: "W" and "S" start at
    # different distances from the pen. Same baseline as the old words.
    pen = ix0 - sized[1][0] * stretch
    baseline = float(iy0 - sized[1][1])
    if stretch == 1.0:
        # Whole-pixel ink edges are too coarse for small text: half a pixel is a third
        # of a stroke.
        pen, baseline = register(found["alpha"], x, y, font, reference, pen, baseline)

    # ponytail: alignment is a guess. A short line centered on the image stays centered;
    # everything else keeps its left edge. Rotated or curved text is drawn level.
    centered = abs((ix0 + ix1) / 2 - W / 2) < 0.03 * W and (ix1 - ix0) < 0.7 * W
    if centered:
        pen = (ix0 + ix1) / 2 - width / 2 - left * stretch
    start = round(pen + left * stretch)
    # Longer words must not run into what follows on the line (a timestamp, the edge of
    # a chat bubble). On a flat background the next non-background column is the limit.
    room = W - 2 - start
    if found["fill"] is not None and not centered:
        band = img[iy0:iy1, ix1:W].astype(np.float32)
        busy = np.flatnonzero((np.linalg.norm(band - found["fill"], axis=2) > MIN_CONTRAST).any(axis=0))
        if len(busy):
            room = min(room, ix1 + int(busy[0]) - (iy1 - iy0) // 2 - start)
    room = max(room, ix1 - ix0)
    # ponytail: text shrinks to fit, down to 60%; it never wraps or grows the bubble.
    fit = max(min(1.0, room / width), 0.6)
    exact = draw_at(font, new_text, pen, baseline) if stretch == 1.0 and fit == 1.0 else None
    if exact:
        blend(img, exact[0], found["color"], exact[1], exact[2])
    else:
        start = max(2, min(start, W - 2 - round(width * fit)))
        size_px = (max(1, round(width * fit)), max(1, round(alpha.shape[0] * fit)))
        alpha = cv2.resize(alpha, size_px, interpolation=cv2.INTER_AREA)
        blend(img, alpha, found["color"], start, round(baseline + top * fit))
    return {"face": face, "size": size * fit, "color": tuple(found["color"])}


def edit(png, replacements):
    source = Image.open(io.BytesIO(png))
    rgba = np.array(source.convert("RGBA"))
    img = np.ascontiguousarray(rgba[:, :, :3])
    faces = installed_faces()
    for r in replacements:
        replace(img, r, faces)
    rgba[:, :, :3] = img
    out = io.BytesIO()
    Image.fromarray(rgba if source.mode in ("RGBA", "LA", "PA") else img).save(out, format="PNG")
    return out.getvalue()


def main():
    request = json.load(sys.stdin)
    sys.stdout.buffer.write(edit(base64.b64decode(request["image"]), request["replacements"]))


if __name__ == "__main__":
    main()
