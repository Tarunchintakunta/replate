"""Keep original pixels for letters that stay; draw only the letters that change.

Characters shared with the original string keep their pixels. Only the ink of
characters that change or move is erased. New characters are page letters at
their natural width, scaled uniformly to this line's ink height (never
stretched to the old span), recoloured from their own print to this line's
paper and ink, and blurred to this line's edge softness. A letter the page
never printed is drawn from the closest bundled face after its stroke width,
colour, outline, grain and blur are matched, and is reported as synthesized.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.rendering.glyph_bank import (
    GlyphBank,
    _binarize,
    _nearly_horizontal,
    _order_quad,
    ink_band,
    line_colors,
    segment_letters,
    segment_respaced,
)

Inpaint = Callable[[np.ndarray, np.ndarray], np.ndarray]


@dataclass
class Preserved:
    image: np.ndarray
    synthesized: str  # characters drawn from a bundled face, not cut from the page
    rescaled: str = ""  # page letters enlarged or shrunk noticeably (from a different text size)


@dataclass
class _Item:
    kind: str  # "copy" | "glyph" | "space"
    width: int
    first: int | None = None  # source index of the first / last character it carries
    last: int | None = None
    x0: int = 0  # copy: source columns
    rgb: np.ndarray | None = None  # glyph: float32 BGR patch
    alpha: np.ndarray | None = None  # glyph: float32 0..1
    dy: int = 0  # glyph: patch top relative to the line's ink top
    lead: int = 0  # glyph: columns left of the letter box inside the patch
    synthetic: bool = False
    restyled: bool = False  # recoloured or synthesized, so it lacks this line's row fade
    rescaled: bool = False  # page letter from a noticeably different text size
    clone: bool = False  # copy of letters printed elsewhere on this line; the originals stay
    x: int = 0


@dataclass
class _Style:
    top: int
    line_h: int
    paper: np.ndarray
    ink: np.ndarray
    outline: np.ndarray | None
    outline_px: int
    stroke: float
    letter_gap: int
    space_w: int
    noise: float
    source: str = ""
    profile: tuple = ()
    scale: float = 1.0
    lean: float = 0.0


def preserve_line(
    working_bgr: np.ndarray,
    reference_bgr: np.ndarray,
    polygon: np.ndarray,
    source_text: str,
    new_text: str,
    bank: GlyphBank,
    *,
    inpaint: Inpaint | None = None,
    font_path: Path | None = None,
    align: str = "left",
) -> Preserved | None:
    source = " ".join(source_text.split())
    new = " ".join(new_text.split())
    if not source or not new:
        return None
    frame = _frame(reference_bgr, polygon)
    if frame is None:
        return None
    reference, ink, shape, warp = frame
    band = ink_band(ink)
    if band is None:
        return None
    ink = ink.copy()
    ink[: band[0]] = False
    ink[band[1] :] = False
    cut = segment_respaced(ink, source)
    if cut is None:
        return None
    new = _respace_new(source, new, cut[2])
    source, (spans, owner) = cut[0], cut[1]
    style = _measure(reference, ink, spans, source)
    if style is None:
        return None
    # A line edited before is rebuilt from the original page, not stacked on.
    restored = _restore_line(working_bgr, reference_bgr, polygon)
    base = _warp_like(restored, warp, reference.shape)

    fitted: list = []

    def face():
        if not fitted:
            fitted.append(_fit_face(reference, ink, spans, source, style, font_path))
        return fitted[0]

    items: list[_Item] = []
    synthesized: list[str] = []
    rescaled: list[str] = []
    changed: list[int] = []  # source characters whose ink must go
    for tag, i1, i2, j1, j2 in SequenceMatcher(a=source, b=new, autojunk=False).get_opcodes():
        if tag == "equal":
            x0, x1 = spans[i1][0], spans[i2 - 1][1]
            items.append(_Item("copy", x1 - x0, first=i1, last=i2 - 1, x0=x0))
            continue
        changed.extend(range(i1, i2))
        k = j1
        while k < j2:
            char = new[k]
            k += 1
            if char.isspace():
                items.append(_Item("space", style.space_w))
                continue
            run = _printed_run(source, new, k - 1, j2)
            if run is not None:
                # The line already prints these letters together: copy them with their
                # own spacing and joins instead of rebuilding them one by one.
                at, length = run
                x0, x1 = spans[at][0], spans[at + length - 1][1]
                items.append(_Item("copy", x1 - x0, first=at, last=at + length - 1, x0=x0, clone=True))
                k += length - 1
                continue
            item = _glyph(bank, char, style, face, line=source)
            if item is None:
                return None
            if item.synthetic and char not in synthesized:
                synthesized.append(char)
            if item.rescaled and char not in rescaled:
                rescaled.append(char)
            items.append(item)
    if not items:
        return None

    left, right = spans[0][0], spans[-1][1]
    _layout(items, spans, style, left)
    lo, hi = _surface_limits(reference, shape, style)
    if _fit_width(items, spans, style, lo, hi, left, right, align):
        # Still too long for the surface it is printed on: scale the whole word
        # uniformly (never one axis), so old and new letters stay one size.
        width = items[-1].x + items[-1].width - left
        factor = max(0.55, (hi - lo) / max(width, 1))
        converted = []
        for index, it in enumerate(items):
            if it.kind == "copy":
                items[index] = _copy_as_glyph(it, reference, owner, style.top)
                if not it.clone:
                    converted.extend(range(it.first, it.last + 1))
        for it in items:
            if it.kind == "glyph":
                _scale_glyph(it, factor, style.line_h)
            else:
                it.width = max(1, int(round(it.width * factor)))
        style.letter_gap = int(round(style.letter_gap * factor))
        style.scale = factor
        changed.extend(converted)
        _layout(items, spans, style, left)
        _shift_into(items, lo, hi, left, right, align)

    moved = [it for it in items if it.kind == "copy" and (it.x != it.x0 or it.clone)]
    for it in moved:
        if not it.clone:
            changed.extend(range(it.first, it.last + 1))
    erase = np.isin(owner, changed).astype(np.uint8)
    if erase.any():
        # Thick painted strokes carry wide soft edges and shading; grow with the stroke.
        k = max(7, int(round(style.stroke * 0.5)) | 1)
        erase = cv2.dilate(erase * 255, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
        erase = cv2.bitwise_and(erase, cv2.dilate(shape, np.ones((5, 5), np.uint8)))
        # Inpaint on the page, not the thin line strip, so the model sees what is
        # around the letters (sign edges, paper grain, shading).
        page_mask = _unwarp_mask(erase, warp, working_bgr.shape[:2])
        base = _warp_like((inpaint or _telea)(restored, page_mask), warp, reference.shape)

    canvas = base.copy()
    for it in moved:
        _paste_letters(canvas, reference, np.isin(owner, range(it.first, it.last + 1)), it.x0, it.x, it.width)
    glyphs = [it for it in items if it.kind == "glyph"]
    if glyphs:
        canvas = _paint(canvas, glyphs, reference, ink, spans, changed or list(range(len(spans))), style, owner)
    return Preserved(_unwarp(working_bgr, canvas, warp), "".join(synthesized), "".join(rescaled))


def _printed_run(source: str, new: str, start: int, end: int) -> tuple[int, int] | None:
    """Longest stretch new[start:...] (2+ letters, no edge spaces) that the line already prints."""
    for length in range(end - start, 1, -1):
        piece = new[start : start + length]
        if piece[0].isspace() or piece[-1].isspace():
            continue
        at = source.find(piece)
        if at >= 0:
            return at, length
    return None


def _respace_new(source: str, new: str, inserted: tuple[int, ...]) -> str:
    """Put the spaces OCR missed into the new text wherever that unchanged stretch survives,
    so the printed gap is copied rather than closed."""
    for i in sorted(inserted, reverse=True):
        left, right = source[max(0, i - 4) : i], source[i : i + 4]
        at = new.find(left + right)
        if at >= 0:
            new = new[: at + len(left)] + " " + new[at + len(left) :]
    return new


# ---------------------------------------------------------------- layout


def _layout(items: list[_Item], spans, style: _Style, left: int) -> None:
    x = left
    for index, it in enumerate(items):
        if index:
            x += _gap(items[index - 1], it, spans, style)
        it.x = x
        x += it.width


def _gap(prev: _Item, cur: _Item, spans, style: _Style) -> int:
    if prev.kind == "space" or cur.kind == "space":
        return 0
    if prev.last is not None and cur.first is not None and cur.first == prev.last + 1:
        return int(round((spans[cur.first][0] - spans[prev.last][1]) * style.scale))
    # Next to a space span the original gap is already inside the space.
    return style.letter_gap


def _fit_width(items, spans, style: _Style, lo: int, hi: int, left: int, right: int, align: str) -> bool:
    """Keep alignment; if too wide, tighten tracking. True when it still does not fit."""
    room = hi - lo
    glyphs = [it for it in items if it.kind == "glyph"]
    width = items[-1].x + items[-1].width - left
    if width > room and glyphs:
        pairs = max(1, len(glyphs) - 1)
        squeeze = min(int(np.ceil((width - room) / pairs)), max(0, style.letter_gap - style.letter_gap // 3))
        style.letter_gap = max(0, style.letter_gap - squeeze)
        _layout(items, spans, style, left)
        width = items[-1].x + items[-1].width - left
    if width > room:
        return True
    _shift_into(items, lo, hi, left, right, align)
    return False


def _shift_into(items, lo: int, hi: int, left: int, right: int, align: str) -> None:
    width = items[-1].x + items[-1].width - left
    shift = _aligned_start(left, right, width, align) - left
    shift = int(np.clip(shift, lo - left, hi - (left + width)))
    for it in items:
        it.x += shift


def _surface_limits(reference: np.ndarray, shape: np.ndarray, style: _Style) -> tuple[int, int]:
    """How far a longer line may run: into the frame margin only where the surface continues.

    Past a sign's edge the colour changes; there the line must stay inside.
    """
    cols = np.flatnonzero(shape.any(axis=0))
    if cols.size == 0:
        return 2, reference.shape[1] - 2
    inner_lo, inner_hi = int(cols[0]), int(cols[-1]) + 1
    band = reference[style.top : style.top + style.line_h].astype(np.float32)
    margin = max(2, int(style.line_h * 0.15))

    def same_surface(a: int, b: int) -> bool:
        if b - a < 3:
            return False
        strip = band[:, a:b].reshape(-1, 3)
        return float(np.linalg.norm(np.median(strip, axis=0) - style.paper)) < 40

    lo = 2 if same_surface(0, inner_lo) else max(2, inner_lo - margin)
    hi = reference.shape[1] - 2 if same_surface(inner_hi, reference.shape[1]) else min(reference.shape[1] - 2, inner_hi + margin)
    return lo, hi


def _copy_as_glyph(it: _Item, reference: np.ndarray, owner: np.ndarray, top: int) -> _Item:
    """An unchanged letter block as a movable, scalable layer of its own pixels."""
    pad = 3
    a, b = max(0, it.x0 - pad), min(reference.shape[1], it.x0 + it.width + pad)
    mask = np.isin(owner[:, a:b], range(it.first, it.last + 1)).astype(np.uint8) * 255
    mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    alpha = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (0, 0), 0.8)
    return _Item(
        "glyph",
        width=it.width,
        first=it.first,
        last=it.last,
        rgb=reference[:, a:b].astype(np.float32),
        alpha=alpha,
        dy=-top,
        lead=it.x0 - a,
        x=it.x,
    )


def _aligned_start(left: int, right: int, width: int, align: str) -> int:
    # Unchanged letters stay where they were printed. A centred line drifts by
    # half the length change, which is far less visible than re-laid letters.
    # Right-aligned lines (price columns) keep their right edge.
    if align == "right":
        return right - width
    return left


def _scale_glyph(it: _Item, factor: float, line_h: int) -> None:
    """Uniform scale, both axes, kept on the line's baseline."""
    h, w = it.alpha.shape
    nh, nw = max(1, int(round(h * factor))), max(1, int(round(w * factor)))
    it.rgb = cv2.resize(it.rgb, (nw, nh), interpolation=cv2.INTER_AREA)
    it.alpha = cv2.resize(it.alpha, (nw, nh), interpolation=cv2.INTER_AREA)
    bottom = it.dy + h
    it.dy = int(round(line_h - (line_h - bottom) * factor)) - nh
    it.lead = int(round(it.lead * factor))
    it.width = max(1, int(round(it.width * factor)))


# ---------------------------------------------------------------- letters


def _glyph(bank: GlyphBank, char: str, style: _Style, face, line: str = "") -> _Item | None:
    if char in bank.samples:
        own = [item for item in bank.samples[char] if line and item.line == line]
        pool = _drop_miscuts(own or bank.samples[char], char, face)
        sample = _pick_like(pool, style)
        # The real letter shape beats a font guess, even from a smaller print of the
        # same face; beyond ~2x the enlargement itself becomes visible.
        if sample.patch is not None and 0.5 <= style.line_h / max(sample.line_h, 1) <= 2.2:
            return _from_sample(sample, style)
    return _synthesize(char, style, face() if callable(face) else face)


def _drop_miscuts(samples, char: str, face):
    """Touching letters are sometimes cut off-centre (half an m passing for a p).
    With more than one copy, keep those whose shape agrees with the line's identified face."""
    if len(samples) < 2:
        return samples
    from app.rendering import font_library

    fitted = face() if callable(face) else face
    rendered = font_library.render_glyph(fitted.path, char, 96) if fitted is not None else None
    target = font_library.glyph_features(rendered[0] > 0.5) if rendered is not None else None
    if target is None:
        return samples

    def agreement(sample) -> float:
        mine = font_library.glyph_features(sample.mask) if sample.mask is not None else None
        if mine is None:
            return 0.0
        iou = float(np.minimum(mine[0], target[0]).sum() / max(np.maximum(mine[0], target[0]).sum(), 1e-6))
        return iou * float(np.exp(-2.0 * abs(np.log(max(mine[1], 1e-3) / max(target[1], 1e-3)))))

    scores = [agreement(item) for item in samples]
    best = max(scores)
    return [item for item, score in zip(samples, scores) if score >= best - 0.1]


def _pick_like(samples, style: _Style):
    """The page copy of a letter that best matches this line: size, ink colour and weight."""
    line_weight = style.stroke / max(style.line_h, 1)

    def cost(sample) -> float:
        size = abs(np.log(max(sample.line_h, 1) / max(style.line_h, 1)))
        ink = sample.ink_bgr if sample.ink_bgr is not None else style.ink
        color = float(np.linalg.norm(ink - style.ink)) / 120.0
        if getattr(sample, "weight", None) is None:
            mask = sample.mask if sample.mask is not None else sample.rgba[:, :, 3] > 127
            sample.weight = _stroke_width(mask.astype(np.float32)) / max(sample.line_h, 1)
        weight = abs(np.log(max(sample.weight, 1e-3) / max(line_weight, 1e-3)))
        if getattr(sample, "lean", None) is None:
            mask = (sample.mask if sample.mask is not None else sample.rgba[:, :, 3] > 127).astype(np.uint8)
            sample.lean = _lean(mask)
        lean = abs(sample.lean - style.lean)
        return size + color + 1.5 * weight + 4.0 * lean

    return min(samples, key=cost)


def _lean(mask: np.ndarray) -> float:
    """Italic lean of a letter or line: the shear that makes its strokes most vertical."""
    if int(mask.sum()) < 30:
        return 0.0
    best, best_score = 0.0, -1.0
    for shear in np.linspace(-0.45, 0.45, 19):
        columns = _shear(mask, -shear, mask.shape[0]).sum(axis=0).astype(np.float64)
        score = float((columns**2).sum())
        if score > best_score:
            best, best_score = float(shear), score
    return best


def _from_sample(sample, style: _Style) -> _Item:
    scale = style.line_h / max(sample.line_h, 1)
    patch = sample.patch.astype(np.float32)
    rgb = _recolor(patch, sample.paper_bgr, sample.ink_bgr, style)
    restyled = rgb is not patch
    mask = sample.mask.astype(np.uint8) * 255
    mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    alpha = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (0, 0), 0.7)
    if abs(scale - 1.0) > 0.03:
        h, w = alpha.shape
        size = (max(1, int(round(w * scale))), max(1, int(round(h * scale))))
        interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
        rgb = cv2.resize(rgb, size, interpolation=interpolation)
        alpha = np.clip(cv2.resize(alpha, size, interpolation=interpolation), 0, 1)
        if scale > 1.2:
            # Enlarging softens the letter outline; restore its crispness (shape only, not tone).
            amount = min(1.0, 0.5 * (scale - 1.0))
            alpha = np.clip(alpha + amount * (alpha - cv2.GaussianBlur(alpha, (0, 0), 0.6 * scale)), 0, 1)
        if abs(scale - 1.0) > 0.2 and style.stroke > 0:
            # Print weight does not scale with size (dot-matrix dots, pen width): re-match it.
            alpha = _match_stroke_inplace(alpha, style.stroke)
    return _Item(
        "glyph",
        width=max(1, int(round(sample.rgba.shape[1] * scale))),
        rgb=rgb,
        alpha=alpha,
        dy=int(round((sample.top - sample.pad_top) * scale)),
        lead=int(round(sample.pad_left * scale)),
        restyled=restyled,
        rescaled=abs(np.log(scale)) > np.log(1.25),
    )


def _recolor(patch: np.ndarray, paper: np.ndarray, ink: np.ndarray, style: _Style) -> np.ndarray:
    """Same print: keep the pixels. Other print: map paper->paper and ink->ink along that axis."""
    if paper is None or ink is None:
        return patch
    if np.abs(paper - style.paper).max() < 6 and np.abs(ink - style.ink).max() < 6:
        return patch
    axis = ink - paper
    norm = float(axis @ axis)
    if norm < 1.0:
        return patch
    t = np.clip(((patch - paper) @ axis) / norm, -0.2, 1.3)[..., None]
    residual = patch - paper - t * axis
    return np.clip(style.paper + t * (style.ink - style.paper) + 0.5 * residual, 0, 255)


@dataclass
class _Face:
    path: Path
    size: int
    baseline: int  # frame row of the baseline
    slant: float  # horizontal shift per row above the baseline (italic lean)


def _fit_face(reference, ink, spans, source: str, style: _Style, fallback: Path | None) -> _Face | None:
    """Closest open font for this line, sized and placed from the line's own letters."""
    from app.rendering import font_library

    slant = _slant(ink, style)
    upright = _shear(ink.astype(np.uint8), -slant, style.top + style.line_h) > 0
    samples: dict[str, tuple[np.ndarray, int]] = {}
    for char, (a, b) in zip(source, spans):
        if char.isspace() or char in samples:
            continue
        lo, hi = max(0, a - 2), min(upright.shape[1], b + 2)
        piece = upright[:, lo:hi]
        rows = np.flatnonzero(piece.any(axis=1))
        if rows.size >= 4:
            samples[char] = (piece[rows[0] : rows[-1] + 1], int(rows[0]))
    ranked = font_library.best_font({c: m for c, (m, _t) in samples.items()}) if samples else []
    path = ranked[0][0] if ranked else (fallback if fallback and Path(fallback).is_file() else _default_font())
    if path is None:
        return None
    ratios, tops = [], []
    for char, (mask, top) in samples.items():
        glyph = font_library.render_glyph(path, char, 100)
        if glyph is not None:
            ratios.append(mask.shape[0] / glyph[0].shape[0])
            tops.append((top, glyph[1]))
    if not ratios:
        size = max(6, int(round(style.line_h * 1.3)))
        return _Face(path, size, style.top + style.line_h, slant)
    size = max(6, int(round(100 * float(np.median(ratios)))))
    baseline = float(np.median([top - rel * size / 100 for top, rel in tops]))
    return _Face(path, size, int(round(baseline)), slant)


def _slant(ink: np.ndarray, style: _Style) -> float:
    """Italic lean: the shear that makes vertical strokes line up in the column profile."""
    band = ink[style.top : style.top + style.line_h].astype(np.uint8)
    if band.sum() < 50:
        return 0.0
    best, best_score = 0.0, -1.0
    for shear in np.linspace(-0.45, 0.45, 37):
        columns = _shear(band, -shear, band.shape[0]).sum(axis=0).astype(np.float64)
        score = float((columns**2).sum())
        if score > best_score:
            best, best_score = float(shear), score
    return best if abs(best) >= 0.04 else 0.0


def _shear(image: np.ndarray, slant: float, base_row: float) -> np.ndarray:
    """Shift each row by slant * (rows above base_row). Positive slant leans right."""
    if slant == 0:
        return image
    pad = int(np.ceil(abs(slant) * image.shape[0])) + 2
    matrix = np.float32([[1, -slant, slant * base_row + pad], [0, 1, 0]])
    out = cv2.warpAffine(image, matrix, (image.shape[1] + 2 * pad, image.shape[0]), flags=cv2.INTER_LINEAR)
    return out[:, pad : pad + image.shape[1]]


def _synthesize(char: str, style: _Style, face: _Face | None) -> _Item | None:
    from app.rendering import font_library

    if face is None:
        return None
    glyph = font_library.render_glyph(face.path, char, face.size)
    if glyph is None:
        return None
    alpha, top_rel = glyph
    alpha = _match_stroke(alpha, style.stroke)
    margin = 6 + int(np.ceil(abs(face.slant) * alpha.shape[0]))
    alpha = np.pad(alpha, ((6, 6), (margin, margin)))
    top = face.baseline + top_rel - 6
    if face.slant:
        alpha = _shear(alpha, face.slant, face.baseline - top)
        cols = np.flatnonzero(alpha.max(axis=0) > 0.05)
        alpha = alpha[:, max(0, cols[0] - 2) : cols[-1] + 3]
    cols = np.flatnonzero(alpha.max(axis=0) > 0.1)
    if cols.size == 0:
        return None
    rgb, alpha = _profile_paint(alpha, style)
    if style.noise > 0:
        rng = np.random.default_rng(abs(hash(char)) % (2**32))
        grain = cv2.GaussianBlur(rng.normal(0, style.noise, alpha.shape).astype(np.float32), (0, 0), 0.6)
        rgb = rgb + grain[..., None]
    return _Item(
        "glyph",
        width=int(cols[-1] - cols[0] + 1),
        rgb=np.clip(rgb, 0, 255),
        alpha=np.clip(alpha, 0, 1),
        dy=top - style.top,
        lead=int(cols[0]),
        synthetic=True,
        restyled=True,
    )


def _profile_paint(alpha: np.ndarray, style: _Style) -> tuple[np.ndarray, np.ndarray]:
    """Colour a letter by distance from its edge, using the line's own edge-to-core colours.

    This carries soft edges, outlines, inner shading and a halo from the
    printed letters to the new one instead of one flat colour.
    """
    binary = (alpha > 0.5).astype(np.uint8)
    inside = cv2.distanceTransform(binary, cv2.DIST_L2, 3)
    outside = cv2.distanceTransform(1 - binary, cv2.DIST_L2, 3)
    signed = np.where(binary > 0, inside, -outside)
    d, colors = style.profile
    rgb = np.stack([np.interp(signed, d, colors[:, c]) for c in range(3)], axis=-1).astype(np.float32)
    span = float(np.linalg.norm(style.ink - style.paper)) or 1.0
    halo = np.linalg.norm(rgb - style.paper, axis=2) / span
    fade = np.clip((signed - d[0]) / max(-d[0], 1.0), 0, 1)  # 0 at the outermost step
    alpha_out = np.where(binary > 0, np.maximum(alpha, 0.0), np.clip(halo, 0, 1) * fade)
    alpha_out = np.maximum(alpha_out, alpha)
    return rgb, alpha_out.astype(np.float32)


def _edge_profile(reference: np.ndarray, ink: np.ndarray, paper: np.ndarray, core: np.ndarray):
    """Median colour at each signed distance from the ink edge (outside negative)."""
    binary = ink.astype(np.uint8)
    inside = cv2.distanceTransform(binary, cv2.DIST_L2, 3)
    outside = cv2.distanceTransform(1 - binary, cv2.DIST_L2, 3)
    signed = np.where(binary > 0, inside, -outside)
    top = max(1.0, float(np.percentile(inside[binary > 0], 95))) if binary.any() else 1.0
    steps = np.arange(-4.0, top + 1.0, 1.0)
    colors = []
    for step in steps:
        near = np.abs(signed - step) < 0.5
        colors.append(np.median(reference[near].astype(np.float32), axis=0) if int(near.sum()) >= 6 else None)
    for i, color in enumerate(colors):
        if color is None:
            colors[i] = paper if steps[i] < 0 else core
    return steps, np.array(colors, np.float32)


def _default_font() -> Path | None:
    from app.rendering.fonts import resolve_font

    return resolve_font("sans", False)


def _stroke_width(mask: np.ndarray) -> float:
    """Typical stroke thickness: twice the inner distance near the stroke cores.

    Rough painted edges and pinholes inflate a perimeter-based estimate, so the
    mask is closed first and the distance transform is read at its upper range.
    """
    binary = (mask > 0.5).astype(np.uint8)
    if int(binary.sum()) < 8:
        return 0.0
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    distance = cv2.distanceTransform(binary, cv2.DIST_L2, 3)
    return 2.0 * float(np.percentile(distance[binary > 0], 90))


def _match_stroke_inplace(alpha: np.ndarray, target: float) -> np.ndarray:
    """Thin or thicken a letter alpha without changing its canvas size.

    Bounded: at most a third of the current stroke per side, and never so far
    that the letter fills its box or vanishes.
    """
    area = float((alpha > 0.5).sum())
    for _ in range(3):
        current = _stroke_width(alpha)
        delta = target - current
        if abs(delta) < 0.8 or current <= 0:
            break
        radius = max(1, min(int(round(abs(delta) / 2)), int(current / 3) or 1))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))
        changed = cv2.dilate(alpha, kernel) if delta > 0 else cv2.erode(alpha, kernel)
        grown = float((changed > 0.5).sum()) / max(area, 1.0)
        if float(changed.max()) < 0.5 or not 0.5 <= grown <= 1.6:
            break
        alpha = changed
    return alpha


def _match_stroke(alpha: np.ndarray, target: float) -> np.ndarray:
    if target <= 0:
        return alpha
    pad = int(np.ceil(target)) + 4
    alpha = np.pad(alpha, pad)
    for _ in range(4):
        delta = target - _stroke_width(alpha)
        if abs(delta) < 0.8:
            break
        # Morphology moves each side by r, so the stroke changes by about 2r.
        radius = max(1, int(round(abs(delta) / 2)))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))
        thinner = cv2.erode(alpha, kernel)
        if delta < 0 and float(thinner.max()) < 0.5:
            break  # would erase the letter
        alpha = cv2.dilate(alpha, kernel) if delta > 0 else thinner
    ys, xs = np.where(alpha > 0.05)
    return alpha[pad:-pad, xs.min() : xs.max() + 1] if xs.size else alpha[pad:-pad]


# ---------------------------------------------------------------- paint


def _paint(canvas, glyphs, reference, ink, spans, donors, style: _Style, owner=None) -> np.ndarray:
    """Composite new letters, then pick the blur that matches the replaced letters' edges."""
    height, width = canvas.shape[:2]
    rgb_acc = np.zeros(canvas.shape, np.float32)
    alpha_acc = np.zeros(canvas.shape[:2], np.float32)
    gain = _row_gain(reference, ink, spans, donors)
    donor_color = _donor_lookup(reference, ink, spans, donors, owner)
    for it in glyphs:
        y0 = style.top + it.dy
        x0 = it.x - it.lead
        h, w = it.alpha.shape
        ty0, tx0 = max(0, y0), max(0, x0)
        ty1, tx1 = min(height, y0 + h), min(width, x0 + w)
        if ty1 <= ty0 or tx1 <= tx0:
            continue
        a = it.alpha[ty0 - y0 : ty1 - y0, tx0 - x0 : tx1 - x0]
        if it.restyled:
            a = a * gain[ty0:ty1, None]
        c = it.rgb[ty0 - y0 : ty1 - y0, tx0 - x0 : tx1 - x0]
        if it.synthetic and donor_color is not None:
            c = _take_texture(c, it.alpha[ty0 - y0 : ty1 - y0, tx0 - x0 : tx1 - x0], donor_color[ty0:ty1, tx0:tx1])
        region = alpha_acc[ty0:ty1, tx0:tx1]
        take = a > region
        rgb_acc[ty0:ty1, tx0:tx1][take] = c[take]
        alpha_acc[ty0:ty1, tx0:tx1] = np.maximum(region, a)
    columns = np.flatnonzero(alpha_acc.max(axis=0) > 0.05)
    if columns.size == 0:
        return canvas
    c0, c1 = max(0, columns[0] - 3), min(width, columns[-1] + 4)
    gray_ref = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY).astype(np.float32)
    d0, d1 = spans[min(donors)][0], spans[max(donors)][1]
    target = _otsu_energy(gray_ref[:, d0:d1]) if d1 - d0 > 4 else _otsu_energy(gray_ref)
    base = canvas.astype(np.float32)
    best, best_gap = canvas, 1e9
    for sigma in (0.0, 0.4, 0.7, 1.0, 1.4, 2.0):
        if sigma:
            pre = cv2.GaussianBlur(rgb_acc * alpha_acc[..., None], (0, 0), sigma)
            a = cv2.GaussianBlur(alpha_acc, (0, 0), sigma)
            color = pre / np.maximum(a, 1e-4)[..., None]
        else:
            a, color = alpha_acc, rgb_acc
        image = np.clip(base * (1 - a[..., None]) + color * a[..., None], 0, 255).astype(np.uint8)
        energy = _otsu_energy(cv2.cvtColor(image[:, c0:c1], cv2.COLOR_BGR2GRAY).astype(np.float32))
        gap = abs(energy - target)
        if gap < best_gap:
            best, best_gap = image, gap
    return best


def _donor_lookup(reference, ink, spans, donors, owner=None) -> np.ndarray | None:
    """For every frame pixel, the colour of the nearest ink pixel of the replaced letters.

    Those pixels share the new letter's place, light, paint and grain.
    """
    if owner is not None:
        donor = np.isin(owner, donors).astype(np.uint8)
    else:
        donor = np.zeros(ink.shape, np.uint8)
        for index in donors:
            a, b = spans[index]
            donor[:, a:b] = ink[:, a:b]
    if int(donor.sum()) < 20:
        donor = ink.astype(np.uint8)
    # Stroke cores only, so edge blending does not leak into the fill.
    core = cv2.erode(donor, np.ones((3, 3), np.uint8))
    donor = core if int(core.sum()) >= 20 else donor
    if int(donor.sum()) < 20:
        return None
    _dist, labels = cv2.distanceTransformWithLabels(1 - donor, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    # Labels number the zero pixels of the input (the donor pixels) in scan order from 1.
    order = np.zeros(int(labels.max()) + 1, np.int64)
    flat = np.flatnonzero(donor.ravel() > 0)
    order[1 : flat.size + 1] = flat
    nearest = order[labels]
    # Prefer a donor pixel on the same row: neon tubes, print streaks and light
    # bands run horizontally, and a 2D nearest pixel would bend them.
    width = donor.shape[1]
    columns = np.arange(width)
    for y in range(donor.shape[0]):
        xs = np.flatnonzero(donor[y])
        if xs.size == 0:
            continue
        pos = np.clip(np.searchsorted(xs, columns), 1, max(xs.size - 1, 1))
        left = xs[np.clip(pos - 1, 0, xs.size - 1)]
        right = xs[np.clip(pos, 0, xs.size - 1)]
        pick = np.where(np.abs(columns - left) <= np.abs(right - columns), left, right)
        nearest[y] = y * width + pick
    return reference.reshape(-1, 3)[nearest].astype(np.float32)


def _take_texture(color: np.ndarray, alpha: np.ndarray, donor: np.ndarray) -> np.ndarray:
    """Inside the letter use the replaced letters' real pixels; keep the measured rim colours at the edge."""
    binary = (alpha > 0.5).astype(np.uint8)
    inside = cv2.distanceTransform(binary, cv2.DIST_L2, 3)
    weight = np.clip((inside - 1.0) / 2.0, 0, 1)[..., None]
    # Keep the grain and light of the replaced letters, but not their one-off
    # marks (a scratch or smudge on that letter would look like a defect here).
    deviation = donor - color
    size = np.linalg.norm(deviation, axis=-1, keepdims=True)
    deviation = deviation * np.minimum(1.0, 28.0 / np.maximum(size, 1e-3))
    return color + deviation * weight


def _row_gain(reference, ink, spans, donors) -> np.ndarray:
    """Per-row ink strength of the replaced letters (faded rows, print streaks)."""
    gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY).astype(np.float32)
    d0, d1 = spans[min(donors)][0], spans[max(donors)][1]
    region, mask = gray[:, d0:d1], ink[:, d0:d1]
    gain = np.ones(gray.shape[0], np.float32)
    if int(mask.sum()) < 16 or int((~mask).sum()) < 8:
        return gain
    paper = float(np.median(region[~mask]))
    delta = np.abs(region - paper)
    rows = [y for y in range(region.shape[0]) if mask[y].sum() >= 2]
    if not rows:
        return gain
    values = np.array([delta[y, mask[y]].mean() for y in rows])
    center = float(np.median(values)) or 1.0
    for y, value in zip(rows, values):
        gain[y] = float(np.clip(value / center, 0.55, 1.0))
    return gain


def _otsu_energy(gray: np.ndarray) -> float:
    values = gray.astype(np.uint8)
    _threshold, mask = cv2.threshold(values, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    if float(mask.mean()) > 127:
        mask = cv2.bitwise_not(mask)
    magnitude = np.abs(cv2.Laplacian(values.astype(np.float32), cv2.CV_32F))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    ring = cv2.subtract(cv2.dilate(mask, kernel), cv2.erode(mask, kernel))
    found = magnitude[ring > 0]
    return float(found.mean()) if found.size >= 10 else 0.0


# ---------------------------------------------------------------- measure


def _measure(reference: np.ndarray, ink: np.ndarray, spans, source: str) -> _Style | None:
    rows = np.flatnonzero(ink.any(axis=1))
    if rows.size < 4:
        return None
    top, bottom = int(rows[0]), int(rows[-1]) + 1
    paper, ink_bgr = line_colors(reference, ink)
    outline, outline_px = _outline(reference, ink, ink_bgr)
    gaps = [
        spans[i + 1][0] - spans[i][1]
        for i in range(len(source) - 1)
        if not source[i].isspace() and not source[i + 1].isspace()
    ]
    spaces = [b - a for (a, b), ch in zip(spans, source) if ch.isspace()]
    line_h = bottom - top
    gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY).astype(np.float32)
    residual = gray - cv2.GaussianBlur(gray, (0, 0), 1.1)
    return _Style(
        top=top,
        line_h=line_h,
        paper=paper,
        ink=ink_bgr,
        outline=outline,
        outline_px=outline_px,
        stroke=_stroke_width(ink.astype(np.float32)),
        letter_gap=int(round(np.median(gaps))) if gaps else max(1, line_h // 12),
        space_w=int(round(np.median(spaces))) if spaces else max(3, int(line_h * 0.45)),
        noise=float(residual[ink].std()) if int(ink.sum()) >= 8 else 0.0,
        source=source,
        profile=_edge_profile(reference, ink, paper, ink_bgr),
        lean=_lean(ink[top:bottom].astype(np.uint8)),
    )


def _outline(reference: np.ndarray, ink: np.ndarray, core_bgr: np.ndarray) -> tuple[np.ndarray | None, int]:
    """A boundary ring whose colour is far from the stroke core is an outline."""
    binary = ink.astype(np.uint8)
    distance = cv2.distanceTransform(binary, cv2.DIST_L2, 3)
    ring = (distance > 0) & (distance <= 1.5)
    if int(ring.sum()) < 20 or float(distance.max()) < 3:
        return None, 0
    ring_bgr = np.median(reference[ring].astype(np.float32), axis=0)
    if float(np.linalg.norm(ring_bgr - core_bgr)) < 60:
        return None, 0
    # Anti-aliased edges sit between paper and ink. An outline is off that line.
    paper = np.median(reference[distance == 0].astype(np.float32), axis=0)
    axis = core_bgr - paper
    t = float(np.clip((ring_bgr - paper) @ axis / max(float(axis @ axis), 1.0), 0, 1))
    if float(np.linalg.norm(ring_bgr - (paper + t * axis))) < 40:
        return None, 0
    near = np.linalg.norm(reference.astype(np.float32) - ring_bgr, axis=2) < np.linalg.norm(
        reference.astype(np.float32) - core_bgr, axis=2
    )
    depth = distance[(distance > 0) & near]
    thickness = int(round(float(np.percentile(depth, 75)))) if depth.size else 1
    return ring_bgr, max(1, thickness)


# ---------------------------------------------------------------- frames


def _telea(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    return cv2.inpaint(image, mask, 3, cv2.INPAINT_TELEA)


def _paste_letters(canvas, reference, ink, src_x: int, dst_x: int, width: int) -> None:
    """Move original letters with their own soft edge, not the paper behind them."""
    pad = 3
    s0, s1 = max(0, src_x - pad), min(reference.shape[1], src_x + width + pad)
    d0 = dst_x - (src_x - s0)
    if d0 < 0 or d0 + (s1 - s0) > canvas.shape[1]:
        return
    mask = ink[:, s0:s1].astype(np.uint8) * 255
    mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    alpha = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (0, 0), 0.8)[..., None]
    region = canvas[:, d0 : d0 + (s1 - s0)].astype(np.float32)
    canvas[:, d0 : d0 + (s1 - s0)] = np.clip(region * (1 - alpha) + reference[:, s0:s1] * alpha, 0, 255).astype(np.uint8)


def _frame(image_bgr: np.ndarray, polygon: np.ndarray):
    """Line crop with room on both sides, its ink (inside the polygon only) and the mapping back."""
    points = np.asarray(polygon, dtype=np.float32).reshape(-1, 2)
    if len(points) < 3 or image_bgr.size == 0:
        return None
    height, width = image_bgr.shape[:2]
    if _nearly_horizontal(points):
        line_h = float(points[:, 1].max() - points[:, 1].min())
        pad = int(np.ceil(line_h))
        x0 = max(0, int(np.floor(points[:, 0].min())) - pad)
        y0 = max(0, int(np.floor(points[:, 1].min())))
        x1 = min(width, int(np.ceil(points[:, 0].max())) + pad)
        y1 = min(height, int(np.ceil(points[:, 1].max())))
        if x1 - x0 < 4 or y1 - y0 < 4:
            return None
        crop = image_bgr[y0:y1, x0:x1].copy()
        shape = np.zeros(crop.shape[:2], np.uint8)
        cv2.fillConvexPoly(shape, np.round(points - [x0, y0]).astype(np.int32), 255)
        ink = _binarize(crop, shape)
        if ink is None:
            return None
        return crop, ink, shape, ("box", (x0, y0, x1, y1))
    ordered = _order_quad(points)
    box_w = max(8, int(round(max(np.linalg.norm(ordered[1] - ordered[0]), np.linalg.norm(ordered[2] - ordered[3])))))
    box_h = max(8, int(round(max(np.linalg.norm(ordered[3] - ordered[0]), np.linalg.norm(ordered[2] - ordered[1])))))
    pad = box_h
    destination = np.float32([[pad, 0], [pad + box_w - 1, 0], [pad + box_w - 1, box_h - 1], [pad, box_h - 1]])
    matrix = cv2.getPerspectiveTransform(ordered, destination)
    size = (box_w + 2 * pad, box_h)
    warped = cv2.warpPerspective(image_bgr, matrix, size, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    shape = np.zeros(warped.shape[:2], np.uint8)
    shape[:, pad : pad + box_w] = 255
    ink = _binarize(warped, shape)
    if ink is None:
        return None
    return warped, ink, shape, ("warp", (matrix, size))


def _restore_line(working_bgr: np.ndarray, reference_bgr: np.ndarray, polygon: np.ndarray) -> np.ndarray:
    shape = np.zeros(working_bgr.shape[:2], np.uint8)
    cv2.fillConvexPoly(shape, np.round(np.asarray(polygon, np.float32).reshape(-1, 2)).astype(np.int32), 255)
    shape = cv2.dilate(shape, np.ones((5, 5), np.uint8))
    restored = working_bgr.copy()
    restored[shape > 0] = reference_bgr[shape > 0]
    return restored


def _unwarp_mask(mask: np.ndarray, warp, page_shape) -> np.ndarray:
    kind, data = warp
    full = np.zeros(page_shape, np.uint8)
    if kind == "box":
        x0, y0, x1, y1 = data
        full[y0:y1, x0:x1] = mask
        return full
    matrix, _size = data
    back = cv2.warpPerspective(mask, np.linalg.inv(matrix), (page_shape[1], page_shape[0]), flags=cv2.INTER_NEAREST)
    return cv2.dilate(back, np.ones((3, 3), np.uint8))


def _warp_like(image_bgr: np.ndarray, warp, shape) -> np.ndarray:
    kind, data = warp
    if kind == "box":
        x0, y0, x1, y1 = data
        return image_bgr[y0:y1, x0:x1].copy()
    matrix, size = data
    return cv2.warpPerspective(image_bgr, matrix, size, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def _unwarp(working_bgr: np.ndarray, canvas: np.ndarray, warp) -> np.ndarray:
    output = working_bgr.copy()
    kind, data = warp
    if kind == "box":
        x0, y0, x1, y1 = data
        output[y0:y1, x0:x1] = canvas
        return output
    matrix, size = data
    before = cv2.warpPerspective(working_bgr, matrix, size, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    # Only pixels this edit changed go back, so resampling never blurs the rest.
    changed = (np.abs(canvas.astype(np.int16) - before.astype(np.int16)).max(axis=2) > 2).astype(np.uint8) * 255
    changed = cv2.dilate(changed, np.ones((3, 3), np.uint8))
    inverse = np.linalg.inv(matrix)
    target = (working_bgr.shape[1], working_bgr.shape[0])
    back = cv2.warpPerspective(canvas, inverse, target, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    mask = cv2.warpPerspective(changed, inverse, target, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    weight = (mask.astype(np.float32) / 255.0)[..., None]
    return np.clip(output * (1 - weight) + back * weight, 0, 255).astype(np.uint8)


def change_mask(reference_bgr: np.ndarray, polygon: np.ndarray, source_text: str, new_text: str) -> np.ndarray | None:
    """Page mask over only the letters that change, grown for a longer word. None if the line does not cut."""
    source = " ".join(source_text.split())
    new = " ".join(new_text.split())
    frame = _frame(reference_bgr, polygon)
    if frame is None or not source:
        return None
    reference, ink, shape, warp = frame
    band = ink_band(ink)
    if band is None:
        return None
    ink = ink.copy()
    ink[: band[0]] = False
    ink[band[1] :] = False
    cut = segment_respaced(ink, source)
    if cut is None:
        return None
    new = _respace_new(source, new, cut[2])
    source, spans = cut[0], cut[1][0]
    ops = SequenceMatcher(a=source, b=new, autojunk=False).get_opcodes()
    changed = [(i1, i2, j1, j2) for tag, i1, i2, j1, j2 in ops if tag != "equal"]
    if not changed:
        return None
    left = min(spans[i1][0] if i1 < len(spans) else spans[-1][1] for i1, _i2, _j1, _j2 in changed)
    right = max(spans[max(i1, i2 - 1)][1] if i1 < len(spans) else spans[-1][1] for i1, i2, _j1, _j2 in changed)
    char_w = (spans[-1][1] - spans[0][0]) / max(len(source), 1)
    growth = max(0, len(new) - len(source))
    # Any later unchanged letters would collide with a longer word: free the line to its end.
    if growth:
        right = max(right, spans[-1][1]) + int(char_w * (growth + 0.5))
        style = _measure(reference, ink, spans, source)
        if style is not None:
            lo, hi = _surface_limits(reference, shape, style)
            if right > hi:
                # No room on this surface: let the model redraw the whole word at a size that fits.
                left, right = max(lo, spans[0][0]), hi
    pad = max(2, (band[1] - band[0]) // 8)
    mask = np.zeros(ink.shape, np.uint8)
    mask[max(0, band[0] - pad) : band[1] + pad, max(0, left - pad) : min(ink.shape[1], right + pad)] = 255
    return _unwarp_mask(mask, warp, reference_bgr.shape[:2])
