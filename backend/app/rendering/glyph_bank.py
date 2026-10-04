"""Copy letter shapes from the same page instead of substituting a bundled font.

A thermal receipt face is not in the bundled set. When OCR has already read
the line, the ink can be cut into those characters and reused. Each sample
keeps a padded patch of the real pixels, so soft edges, outlines and fills
travel with the letter, plus its line's paper and ink colour for recolouring.

A line is kept only when the cuts agree with the recognized words. Letters
that do not survive that check are left out of the bank.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from itertools import combinations

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_MIN_CONFIDENCE = 0.85


@dataclass
class GlyphSample:
    rgba: np.ndarray
    line_h: int
    top: int
    # Padded crop of the page around the letter. ``mask`` is this letter's ink
    # inside it; the tight letter box starts at (pad_top, pad_left).
    patch: np.ndarray | None = None
    mask: np.ndarray | None = None
    pad_top: int = 0
    pad_left: int = 0
    paper_bgr: np.ndarray | None = None
    ink_bgr: np.ndarray | None = None
    line: str = ""  # the text of the line it was cut from: same line = same face


@dataclass
class GlyphBank:
    samples: dict[str, list[GlyphSample]] = field(default_factory=dict)
    space_ratios: list[float] = field(default_factory=list)
    gap_ratios: list[float] = field(default_factory=list)

    def add_region(
        self,
        image_bgr: np.ndarray,
        polygon: np.ndarray,
        text: str,
        confidence: float,
    ) -> None:
        if confidence < _MIN_CONFIDENCE:
            return
        cleaned = " ".join(text.split())
        if len(cleaned) < 2:
            return
        prepared = _prepare_line(image_bgr, polygon)
        if prepared is None:
            return
        crop, ink = prepared
        band = ink_band(ink)
        if band is None or band[1] - band[0] < 8:
            return
        top_row, bottom_row = band
        ink = ink.copy()
        ink[:top_row] = False
        ink[bottom_row:] = False
        full_crop, full_ink = crop, ink
        paper_bgr, ink_bgr = line_colors(crop, ink)
        crop = crop[top_row:bottom_row]
        ink = ink[top_row:bottom_row]
        line_h = int(ink.shape[0])
        cut = segment_respaced(ink, cleaned)
        spans, owner = cut[1] if cut is not None else (None, None)
        if cut is not None:
            cleaned = cut[0]
        if spans is None:
            logger.debug("Glyph cuts rejected for %r", cleaned[:40])
            return
        widths = [b - a for (ch, (a, b)) in zip(cleaned, spans) if not ch.isspace() and b > a]
        if not widths:
            return
        median = float(np.median(widths))
        for index, (char, (start, end)) in enumerate(zip(cleaned, spans)):
            if char.isspace():
                self.space_ratios.append((end - start) / line_h)
                continue
            width = end - start
            rows = np.flatnonzero(ink[:, start:end].any(axis=1))
            tall = rows.size >= 0.55 * max(line_h, 1)
            if width > median * 1.7 or (width < median * 0.28 and not tall):
                continue
            char_ink = owner == index
            sample = _sample(crop, char_ink, start, end, line_h)
            if sample is None:
                continue
            full_char = np.zeros(full_ink.shape, bool)
            full_char[top_row:bottom_row] = char_ink
            _attach_patch(sample, full_crop, full_char, top_row, start, end)
            sample.paper_bgr, sample.ink_bgr, sample.line = paper_bgr, ink_bgr, " ".join(cleaned.split())
            self._keep(char, sample)
            if index + 1 < len(cleaned) and not cleaned[index + 1].isspace():
                nxt = spans[index + 1][0]
                self.gap_ratios.append(max(0, nxt - end) / line_h)

    def alphabet(self) -> str:
        return "".join(sorted(self.samples))

    def missing_chars(self, text: str) -> str:
        missing: list[str] = []
        for char in text:
            if char.isspace() or char in self.samples or char in missing:
                continue
            missing.append(char)
        return "".join(missing)

    def render(
        self,
        text: str,
        target_h: int,
        *,
        gap_ratio: float | None = None,
        space_ratio: float | None = None,
        line_gap_ratio: float | None = None,
        color_rgb: tuple[int, int, int] | None = None,
    ) -> np.ndarray | None:
        lines = text.split("\n")
        rendered = [
            self._render_line(
                line,
                target_h,
                gap_ratio=gap_ratio,
                space_ratio=space_ratio,
                color_rgb=color_rgb,
            )
            for line in lines
        ]
        if any(layer is None for layer in rendered):
            return None
        layers = [layer for layer in rendered if layer is not None]
        if len(layers) == 1:
            return layers[0]
        gap = max(1, int(round(max(8, int(target_h)) * (0.35 if line_gap_ratio is None else line_gap_ratio))))
        width = max(layer.shape[1] for layer in layers)
        height = sum(layer.shape[0] for layer in layers) + gap * (len(layers) - 1)
        canvas = np.zeros((height, width, 4), np.uint8)
        top = 0
        for layer in layers:
            canvas[top : top + layer.shape[0], : layer.shape[1]] = layer
            top += layer.shape[0] + gap
        return canvas

    def _render_line(
        self,
        text: str,
        target_h: int,
        *,
        gap_ratio: float | None,
        space_ratio: float | None,
        color_rgb: tuple[int, int, int] | None = None,
    ) -> np.ndarray | None:
        cleaned = " ".join(text.split())
        if not cleaned or self.missing_chars(cleaned):
            return None
        target_h = max(8, int(target_h))
        if space_ratio is None:
            space_ratio = float(np.median(self.space_ratios)) if self.space_ratios else 0.48
        if gap_ratio is None:
            gap_ratio = float(np.median(self.gap_ratios)) if self.gap_ratios else 0.06
        space_w = max(2, int(round(target_h * space_ratio)))
        gap_w = max(1, int(round(target_h * max(0.0, gap_ratio))))
        pieces: list[np.ndarray] = []
        for index, char in enumerate(cleaned):
            if index > 0 and not char.isspace() and not cleaned[index - 1].isspace():
                pieces.append(np.zeros((target_h, gap_w, 4), np.uint8))
            if char.isspace():
                pieces.append(np.zeros((target_h, space_w, 4), np.uint8))
                continue
            placed = _place(self._pick(char, target_h, color_rgb), target_h)
            if placed is None:
                return None
            pieces.append(placed)
        if not pieces:
            return None
        return np.concatenate(pieces, axis=1)

    def _keep(self, char: str, sample: GlyphSample) -> None:
        bucket = self.samples.setdefault(char, [])
        if sum(item.line == sample.line for item in bucket) >= 2:
            return  # every line keeps its own copies; one body text cannot crowd out a heading
        if len(bucket) < 24:
            bucket.append(sample)
            return
        nearest = min(range(len(bucket)), key=lambda item: abs(bucket[item].line_h - sample.line_h))
        if abs(bucket[nearest].line_h - sample.line_h) <= max(3, 0.25 * sample.line_h):
            if abs(bucket[nearest].line_h - sample.line_h) <= 3 and sample.line_h >= bucket[nearest].line_h:
                bucket[nearest] = sample
            return
        # A text size the bucket has not seen: make room by dropping one from the most repeated size.
        sizes = [round(np.log2(max(item.line_h, 1)) * 4) for item in bucket]
        crowded = max(set(sizes), key=sizes.count)
        bucket[sizes.index(crowded)] = sample

    def _pick(self, char: str, target_h: int, color_rgb: tuple[int, int, int] | None = None) -> GlyphSample:
        def rank(sample: GlyphSample) -> tuple[float, float]:
            height_gap = abs(sample.line_h - target_h) / max(target_h, 1)
            if color_rgb is None:
                return (height_gap, 0.0)
            opaque = sample.rgba[:, :, 3] > 128
            if not np.any(opaque):
                return (height_gap, 999.0)
            average = sample.rgba[:, :, :3][opaque].mean(axis=0)
            distance = float(np.max(np.abs(average - np.array(color_rgb))))
            return (round(height_gap, 1), distance)

        return min(self.samples[char], key=rank)


def line_ink_height(image_bgr: np.ndarray, polygon: np.ndarray) -> int | None:
    prepared = _prepare_line(image_bgr, polygon)
    if prepared is None:
        return None
    _crop, ink = prepared
    band = ink_band(ink)
    if band is None or band[1] - band[0] < 8:
        return None
    return band[1] - band[0]


def segment_columns(ink: np.ndarray, text: str) -> list[tuple[int, int]] | None:
    found = segment_letters(ink, text)
    return None if found is None else found[0]


def segment_respaced(ink: np.ndarray, text: str):
    """segment_letters, retrying with a space OCR dropped next to punctuation ("Feedback(to").

    Returns (text as cut, (spans, owner), indices where a space was inserted) or None.
    """
    found = segment_letters(ink, text)
    if found is not None and len(found[0]) == len(text):
        return text, found, ()
    spots = [i for i in range(1, len(text)) if text[i - 1] != " " and text[i] != " " and text[i - 1].isalnum() != text[i].isalnum()]
    for trial in [(i,) for i in spots] + list(combinations(spots, 2))[:60]:
        candidate = text
        for i in sorted(trial, reverse=True):
            candidate = candidate[:i] + " " + candidate[i:]
        found = segment_letters(ink, candidate)
        if found is not None and len(found[0]) == len(candidate):
            return candidate, found, trial
    return None


def segment_letters(ink: np.ndarray, text: str) -> tuple[list[tuple[int, int]], np.ndarray] | None:
    """Column span per character (spaces included) and an owner map: ink pixel -> character index.

    Vertical column cuts first. Letters that overlap horizontally (hand
    lettering, italics, tight kerning) have no clean column gap; then each
    letter is taken as its own connected shape.
    """
    spans = _segment_by_columns(ink, text)
    if spans is not None:
        owner = np.full(ink.shape, -1, np.int32)
        for index, (a, b) in enumerate(spans):
            owner[:, a:b][ink[:, a:b]] = index
        return spans, owner
    return _segment_by_shapes(ink, text)


def _segment_by_shapes(ink: np.ndarray, text: str) -> tuple[list[tuple[int, int]], np.ndarray] | None:
    cleaned = " ".join(text.split())
    words = cleaned.split(" ")
    letters = sum(len(word) for word in words)
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(ink.astype(np.uint8), connectivity=8)
    if count < 2 or letters == 0:
        return None
    order = np.argsort(-stats[1:, cv2.CC_STAT_AREA]) + 1
    areas = stats[order, cv2.CC_STAT_AREA]
    reference = float(np.median(areas[:letters])) if areas.size >= letters else float(np.median(areas))
    big = [int(i) for i in order if stats[i, cv2.CC_STAT_AREA] >= 0.12 * reference]
    small = [int(i) for i in order if stats[i, cv2.CC_STAT_AREA] < 0.12 * reference]

    def box(i: int) -> tuple[int, int]:
        return int(stats[i, cv2.CC_STAT_LEFT]), int(stats[i, cv2.CC_STAT_LEFT] + stats[i, cv2.CC_STAT_WIDTH])

    # A letter painted in two strokes: merge pieces whose columns mostly overlap.
    groups: list[list[int]] = []
    for i in sorted(big, key=lambda j: box(j)[0]):
        a, b = box(i)
        if groups:
            ga = min(box(j)[0] for j in groups[-1])
            gb = max(box(j)[1] for j in groups[-1])
            overlap = min(b, gb) - max(a, ga)
            if overlap > 0.6 * min(b - a, gb - ga):
                groups[-1].append(i)
                continue
        groups.append([i])
    if len(groups) != letters:
        return None
    spans_letters = [(min(box(j)[0] for j in g), max(box(j)[1] for j in g)) for g in groups]
    # Dots and accents join the letter whose columns contain them; the rest is grain.
    for i in small:
        a, b = box(i)
        center = (a + b) / 2
        for g, (ga, gb) in zip(groups, spans_letters):
            if ga <= center <= gb:
                g.append(i)
                break
    gaps = [spans_letters[k + 1][0] - spans_letters[k][1] for k in range(letters - 1)]
    spaces = sorted(range(len(gaps)), key=lambda k: -gaps[k])[: len(words) - 1]
    widths = [b - a for a, b in spans_letters]
    if spaces and min(gaps[k] for k in spaces) < 0.2 * float(np.median(widths)):
        return None
    breaks = sorted(spaces)
    sizes = [len(word) for word in words]
    if [b + 1 for b in breaks] != list(np.cumsum(sizes)[:-1]):
        return None
    owner = np.full(ink.shape, -1, np.int32)
    spans: list[tuple[int, int]] = []
    index = 0
    for k, (group, span) in enumerate(zip(groups, spans_letters)):
        spans.append(span)
        owner[np.isin(labels, group)] = index
        index += 1
        if k in breaks:
            spans.append((span[1], spans_letters[k + 1][0]))
            index += 1
    return (spans, owner) if len(spans) == len(cleaned) else None


def _segment_by_columns(ink: np.ndarray, text: str) -> list[tuple[int, int]] | None:
    """Column span for each character, including spaces. None when the cuts disagree."""
    cleaned = " ".join(text.split())
    words = cleaned.split(" ")
    if not cleaned or ink.ndim != 2 or ink.shape[1] < 4:
        return None
    components = _components(ink)
    if not components:
        return None
    body = [end - start for start, end in components if end - start >= 4]
    if not body:
        return None
    median = float(np.median(body))
    speck = max(3.0, median * 0.30)
    line_h = max(ink.shape[0], 1)
    kept: list[tuple[int, int]] = []
    for start, end in components:
        if end - start >= speck:
            kept.append((start, end))
            continue
        # A narrow full-height stroke is a letter such as I, not a speck.
        rows = np.flatnonzero(ink[:, start:end].any(axis=1))
        if rows.size >= 0.55 * line_h:
            kept.append((start, end))
    components = kept
    if not components:
        return None
    median = float(np.median([end - start for start, end in components]))
    grouped = None
    gaps: list[tuple[int, int]] = []
    for factor in (0.55, 0.45, 0.70, 0.90):
        candidate, candidate_gaps = _group_words(components, max(6.0, median * factor))
        if len(candidate) == len(words):
            grouped = candidate
            gaps = candidate_gaps
            break
    fused = max(end - start for start, end in components) > 3 * line_h  # noise bridging whole words
    if grouped is None and len(words) > 1 and not fused:
        # Tight bold faces: letter gaps of 2px, word gaps of 6px. Take the widest
        # gaps as word breaks when they stand clearly apart from the rest.
        widths = sorted((components[i + 1][0] - components[i][1] for i in range(len(components) - 1)), reverse=True)
        k = len(words) - 1
        if len(widths) >= k:
            word_gap, letter_gap = widths[k - 1], (widths[k] if len(widths) > k else 0)
            if word_gap >= max(3, 1.5 * letter_gap, letter_gap + 2):
                candidate, candidate_gaps = _group_words(components, (word_gap + letter_gap) / 2)
                if len(candidate) == len(words):
                    grouped, gaps = candidate, candidate_gaps
    if grouped is None:
        return None
    pieces: list[tuple[int, int]] = []
    for index, (word, group) in enumerate(zip(words, grouped)):
        fitted = _fit_word(ink, group, word, median)
        if fitted is None:  # touching bold letters: judge widths by this word's own pitch
            fitted = _fit_word(ink, group, word, (group[-1][1] - group[0][0]) / max(len(word), 1))
        if fitted is None:
            return None
        if index:
            pieces.append(gaps[index - 1])
        pieces.extend(fitted)
    if len(pieces) != len(cleaned):
        return None
    return pieces


def _components(ink: np.ndarray, merge_gap: int = 1) -> list[tuple[int, int]]:
    occupied = ink.any(axis=0)
    runs: list[tuple[int, int]] = []
    start = 0
    while start < len(occupied):
        end = start + 1
        while end < len(occupied) and occupied[end] == occupied[start]:
            end += 1
        if occupied[start]:
            runs.append((start, end))
        start = end
    merged: list[tuple[int, int]] = []
    for run_start, run_end in runs:
        if merged and run_start - merged[-1][1] <= merge_gap:
            merged[-1] = (merged[-1][0], run_end)
        else:
            merged.append((run_start, run_end))
    return merged


def _group_words(
    components: list[tuple[int, int]],
    space_gap: float,
) -> tuple[list[list[tuple[int, int]]], list[tuple[int, int]]]:
    groups: list[list[tuple[int, int]]] = [[components[0]]]
    gaps: list[tuple[int, int]] = []
    for index in range(1, len(components)):
        gap = components[index][0] - components[index - 1][1]
        if gap >= space_gap:
            groups.append([components[index]])
            gaps.append((components[index - 1][1], components[index][0]))
        else:
            groups[-1].append(components[index])
    return groups, gaps


def _fit_word(
    ink: np.ndarray,
    components: list[tuple[int, int]],
    word: str,
    median: float,
) -> list[tuple[int, int]] | None:
    pieces = list(components)
    guard = 0
    while len(pieces) > len(word) and guard < 16:
        guard += 1
        best: tuple[int, int] | None = None
        for index in range(len(pieces) - 1):
            gap = pieces[index + 1][0] - pieces[index][1]
            combined = pieces[index + 1][1] - pieces[index][0]
            if combined > median * 1.9:
                continue
            if best is None or gap < best[0]:
                best = (gap, index)
        if best is None:
            return None
        index = best[1]
        pieces = pieces[:index] + [(pieces[index][0], pieces[index + 1][1])] + pieces[index + 2 :]
    guard = 0
    while len(pieces) < len(word) and guard < 16:
        guard += 1
        widths = [end - start for start, end in pieces]
        index = int(np.argmax(widths))
        if widths[index] < median * 1.45:
            return None
        cut = _valley(ink, pieces[index][0], pieces[index][1])
        if cut is None:
            return None
        start, end = pieces[index]
        pieces = pieces[:index] + [(start, cut), (cut, end)] + pieces[index + 1 :]
    if len(pieces) != len(word):
        return None
    line_h = max(ink.shape[0], 1)
    for start, end in pieces:
        width = end - start
        rows = np.flatnonzero(ink[:, start:end].any(axis=1))
        tall = rows.size >= 0.55 * line_h
        if width > median * 1.75 or (width < median * 0.28 and not tall):
            return None
        if float(ink[:, start:end].mean()) < 0.03:
            return None
    return pieces


def _valley(ink: np.ndarray, start: int, end: int) -> int | None:
    columns = ink[:, start:end].sum(axis=0).astype(np.float32)
    if columns.size < 6:
        return None
    left = int(columns.size * 0.28)
    right = max(left + 1, int(columns.size * 0.72))
    window = columns[left:right]
    offset = int(np.argmin(window))
    if float(window[offset]) > 0.62 * float(np.percentile(columns, 75)):
        return None
    cut = start + left + offset
    if cut <= start + 1 or cut >= end - 1:
        return None
    return cut


def _prepare_line(image_bgr: np.ndarray, polygon: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    points = np.asarray(polygon, dtype=np.float32).reshape(-1, 2)
    if len(points) < 3 or image_bgr.size == 0:
        return None
    if _nearly_horizontal(points):
        return _crop_line(image_bgr, points)
    ordered = _order_quad(points)
    width = int(round(max(_length(ordered[1] - ordered[0]), _length(ordered[2] - ordered[3]))))
    height = int(round(max(_length(ordered[3] - ordered[0]), _length(ordered[2] - ordered[1]))))
    width = max(8, width)
    height = max(8, height)
    destination = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
    matrix = cv2.getPerspectiveTransform(ordered, destination)
    warped = cv2.warpPerspective(
        image_bgr,
        matrix,
        (width, height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )
    ink = _binarize(warped, np.ones(warped.shape[:2], np.uint8) * 255)
    if ink is None:
        return None
    return warped, ink


def _crop_line(image_bgr: np.ndarray, points: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    height, width = image_bgr.shape[:2]
    x0 = max(0, int(np.floor(points[:, 0].min())))
    y0 = max(0, int(np.floor(points[:, 1].min())))
    x1 = min(width, int(np.ceil(points[:, 0].max())))
    y1 = min(height, int(np.ceil(points[:, 1].max())))
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    crop = image_bgr[y0:y1, x0:x1]
    shape = np.zeros(crop.shape[:2], np.uint8)
    shifted = points.copy()
    shifted[:, 0] -= x0
    shifted[:, 1] -= y0
    cv2.fillConvexPoly(shape, np.round(shifted).astype(np.int32), 255)
    ink = _binarize(crop, shape)
    if ink is None:
        return None
    return crop, ink


def _binarize(image_bgr: np.ndarray, shape: np.ndarray) -> np.ndarray | None:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    pixels = gray[shape > 0]
    if pixels.size < 20:
        return None
    _threshold, _ = cv2.threshold(pixels, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    dark = (gray < _threshold) & (shape > 0)
    # Background is what touches the box edge. Size alone fails when letters
    # fill most of the box or the line is light-on-dark.
    edge = (shape > 0) & ~(cv2.erode(shape, np.ones((3, 3), np.uint8)) > 0)
    edge_dark = float(dark[edge].mean()) if int(edge.sum()) >= 8 else 0.5
    if abs(edge_dark - 0.5) < 0.15:
        light_ink = float(dark[shape > 0].mean()) > 0.5  # ambiguous edge: smaller set is ink
    else:
        light_ink = edge_dark > 0.5
    ink = ((gray > _threshold) & (shape > 0)) if light_ink else dark
    flat = _flatten_light(gray, shape, light_ink)
    if flat is not None:
        ink = flat
    if int(ink.sum()) < 12:
        return None
    return ink


def _flatten_light(gray: np.ndarray, shape: np.ndarray, light_ink: bool) -> np.ndarray | None:
    """Threshold against the local background, so shade and sunlight across a sign do not read as ink.

    The background is the image with strokes removed: a grey closing (dark ink)
    or opening (light ink) with a kernel wider than any stroke.
    """
    rows = np.flatnonzero(shape.any(axis=1))
    if rows.size < 8:
        return None
    line_h = int(rows[-1] - rows[0] + 1)
    scale = min(1.0, 96.0 / line_h)
    small = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else gray
    k = max(5, int(round(line_h * scale * 0.45)) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    op = cv2.MORPH_OPEN if light_ink else cv2.MORPH_CLOSE
    background = cv2.morphologyEx(small, op, kernel)
    background = cv2.GaussianBlur(background, (0, 0), k / 3)
    if scale < 1:
        background = cv2.resize(background, (gray.shape[1], gray.shape[0]), interpolation=cv2.INTER_LINEAR)
    contrast = (gray.astype(np.int16) - background) if light_ink else (background.astype(np.int16) - gray)
    contrast = np.clip(contrast, 0, 255).astype(np.uint8)
    pixels = contrast[shape > 0]
    if pixels.size < 20 or int(pixels.max()) < 20:
        return None
    threshold, _ = cv2.threshold(pixels, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    ink = (contrast > max(threshold, 12)) & (shape > 0)
    # Clean pinholes in painted strokes and isolated grain.
    ink = cv2.morphologyEx(ink.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)) > 0
    return ink if int(ink.sum()) >= 12 else None


def _sample(
    crop_bgr: np.ndarray,
    ink: np.ndarray,
    start: int,
    end: int,
    line_h: int,
) -> GlyphSample | None:
    sliver = ink[:, start:end]
    rows = np.flatnonzero(sliver.any(axis=1))
    if rows.size == 0:
        return None
    top = int(rows[0])
    bottom = int(rows[-1]) + 1
    patch = crop_bgr[top:bottom, start:end]
    alpha = sliver[top:bottom].astype(np.uint8) * 255
    if patch.size == 0 or alpha.mean() < 12:
        return None
    height, width = alpha.shape
    if height < 0.45 * line_h:
        return None
    # Wider than this is a logo or a merged pair, not one letter.
    if width / max(height, 1) > 1.55:
        return None
    rgba = cv2.cvtColor(patch, cv2.COLOR_BGR2RGBA)
    rgba[:, :, 3] = alpha
    return GlyphSample(rgba=rgba, line_h=line_h, top=top)


def ink_band(ink: np.ndarray) -> tuple[int, int] | None:
    """Rows of the line itself: the connected run of inked rows holding the most ink.

    A polygon often clips the ascenders or descenders of the lines above and
    below. Those bits are separated by blank rows, so they fall outside the run.
    """
    counts = ink.sum(axis=1)
    best: tuple[int, int] | None = None
    best_mass = 0
    y = 0
    while y < len(counts):
        if counts[y] == 0:
            y += 1
            continue
        start = y
        while y < len(counts) and (counts[y] > 0 or (y + 1 < len(counts) and counts[y + 1] > 0)):
            y += 1
        mass = int(counts[start:y].sum())
        if mass > best_mass:
            best, best_mass = (start, y), mass
    return best


def line_colors(crop_bgr: np.ndarray, ink: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Median paper colour around the ink and median colour of the stroke cores."""
    pixels = crop_bgr.reshape(-1, 3).astype(np.float32)
    halo = cv2.dilate(ink.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))) > 0
    paper = pixels[~halo.reshape(-1)]
    paper_bgr = np.median(paper, axis=0) if paper.shape[0] >= 8 else np.percentile(pixels, 70, axis=0)
    distance = cv2.distanceTransform(ink.astype(np.uint8), cv2.DIST_L2, 3)
    core = ink & (distance >= max(1.0, float(np.percentile(distance[ink], 60)))) if int(ink.sum()) else ink
    if int(core.sum()) < 8:
        core = ink
    ink_bgr = np.median(crop_bgr[core].astype(np.float32), axis=0) if int(core.sum()) else paper_bgr
    return paper_bgr.astype(np.float32), ink_bgr.astype(np.float32)


def _attach_patch(sample: GlyphSample, crop: np.ndarray, ink: np.ndarray, row0: int, start: int, end: int) -> None:
    pad = 3
    top, bottom = row0 + sample.top, row0 + sample.top + sample.rgba.shape[0]
    y0, y1 = max(0, top - pad), min(crop.shape[0], bottom + pad)
    x0, x1 = max(0, start - pad), min(crop.shape[1], end + pad)
    mask = np.zeros((y1 - y0, x1 - x0), bool)
    mask[:, start - x0 : end - x0] = ink[y0:y1, start:end]
    sample.patch = crop[y0:y1, x0:x1].copy()
    sample.mask = mask
    sample.pad_top = top - y0
    sample.pad_left = start - x0


def _place(sample: GlyphSample, target_h: int) -> np.ndarray | None:
    scale = target_h / max(sample.line_h, 1)
    height = max(1, int(round(sample.rgba.shape[0] * scale)))
    width = max(1, int(round(sample.rgba.shape[1] * scale)))
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    resized = cv2.resize(sample.rgba, (width, height), interpolation=interpolation)
    top = int(round(sample.top * scale))
    if top + height > target_h:
        top = max(0, target_h - height)
    canvas = np.zeros((target_h, width, 4), np.uint8)
    canvas[top : top + height, :width] = resized
    return canvas


def _nearly_horizontal(points: np.ndarray) -> bool:
    order = np.argsort(points[:, 0])
    left = points[order[: min(2, len(points))]]
    right = points[order[-min(2, len(points)) :]]
    width = float(points[:, 0].max() - points[:, 0].min())
    if width < 1:
        return True
    # Over ~0.6 degrees of tilt the line is warped level first; drawing it
    # straight would leave new letters visibly flatter than the old ones.
    return abs(float(left[:, 1].mean() - right[:, 1].mean())) < max(2.0, width * 0.01)


def _order_quad(points: np.ndarray) -> np.ndarray:
    pts = points.reshape(-1, 2).astype(np.float32)
    if len(pts) != 4:
        _center, _size, _angle = cv2.minAreaRect(pts)
        pts = cv2.boxPoints((_center, _size, _angle))
    sums = pts.sum(axis=1)
    diffs = np.diff(pts, axis=1).reshape(-1)
    ordered = np.stack(
        [
            pts[int(np.argmin(sums))],
            pts[int(np.argmin(diffs))],
            pts[int(np.argmax(sums))],
            pts[int(np.argmax(diffs))],
        ]
    )
    return ordered.astype(np.float32)


def _length(vector: np.ndarray) -> float:
    return float(np.linalg.norm(vector))
