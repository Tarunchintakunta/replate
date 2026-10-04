"""Measure a line, draw a candidate, and adjust until the styles agree.

The replacement string is often different, so the check compares appearance
(size, weight, color, spacing, alignment, position, rotation, opacity, and
a shadow or outline) rather than requiring the same letters. Neural editors
that repaint a whole line were not used: they need a GPU and trained weights.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import cv2
import numpy as np

from app.image.masking import build_text_mask

# Weighted appearance score. The loop stops when the total clears ACCEPT
# and every measured part clears FLOOR.
ACCEPT = 0.84
FLOOR = 0.68
MAX_PASSES = 5


@dataclass
class LineAppearance:
    ink_height: int
    ink_width: int
    stroke_ratio: float
    gap_ratio: float
    space_ratio: float
    line_gap_ratio: float
    color_rgb: tuple[int, int, int]
    opacity: float
    angle_deg: float
    align: str
    shadow: tuple[int, int, tuple[int, int, int]] | None
    outline_px: int
    outline_rgb: tuple[int, int, int] | None
    origin_dx: int = 0
    origin_dy: int = 0


@dataclass
class RenderParams:
    scale: float = 1.0
    tracking: float = 1.0
    word_space: float = 1.0
    dx: int = 0
    dy: int = 0
    opacity: float = 1.0
    dilate: int = 0
    tint_rgb: tuple[int, int, int] | None = None
    shadow: tuple[int, int, tuple[int, int, int]] | None = None
    outline_px: int = 0
    outline_rgb: tuple[int, int, int] | None = None


@dataclass
class MatchReport:
    total: float
    accepted: bool
    passes: int
    parts: dict[str, float]

    @property
    def percent(self) -> int:
        return int(round(self.total * 100))


def measure_appearance(
    image_bgr: np.ndarray,
    polygon: np.ndarray,
    *,
    align: str = "left",
    line_gap_ratio: float = 0.35,
) -> LineAppearance | None:
    _mask, tight = build_text_mask(image_bgr, polygon)
    ys, xs = np.where(tight > 0)
    if xs.size < 12:
        return None
    ink_height = int(ys.max() - ys.min() + 1)
    ink_width = int(xs.max() - xs.min() + 1)
    if ink_height < 6:
        return None
    distance = cv2.distanceTransform((tight > 0).astype(np.uint8), cv2.DIST_L2, 3)
    stroke = float(np.median(distance[tight > 0])) * 2.0
    gap_ratio, space_ratio = _spacing_ratios(tight[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1], ink_height)
    color = _median_rgb(image_bgr, tight)
    opacity = _opacity(image_bgr, polygon, tight)
    angle = _quad_angle(polygon)
    shadow, outline_px, outline_rgb = _effects(image_bgr, tight, polygon)
    origin_dx, origin_dy = _placement_offset(tight, polygon, align if align in {"left", "center", "right"} else "left")
    return LineAppearance(
        ink_height=ink_height,
        ink_width=ink_width,
        stroke_ratio=stroke / ink_height,
        gap_ratio=gap_ratio,
        space_ratio=space_ratio,
        line_gap_ratio=line_gap_ratio,
        color_rgb=color,
        opacity=opacity,
        angle_deg=angle,
        align=align if align in {"left", "center", "right"} else "left",
        shadow=shadow,
        outline_px=outline_px,
        outline_rgb=outline_rgb,
        origin_dx=origin_dx,
        origin_dy=origin_dy,
    )


def initial_params(appearance: LineAppearance) -> RenderParams:
    return RenderParams(
        dx=appearance.origin_dx,
        dy=appearance.origin_dy,
        opacity=1.0,
    )


def decorate(layer: np.ndarray, params: RenderParams) -> np.ndarray:
    """Apply weight, tint, opacity, outline, and shadow to an RGBA patch."""
    image = layer.copy()
    if params.dilate:
        image = _dilate_ink(image, params.dilate)
    if params.tint_rgb is not None:
        image = _tint(image, params.tint_rgb)
    if params.opacity < 0.99:
        image[:, :, 3] = np.clip(image[:, :, 3].astype(np.float32) * params.opacity, 0, 255).astype(np.uint8)
    if params.outline_px > 0 and params.outline_rgb is not None:
        image = _outline(image, params.outline_px, params.outline_rgb)
    if params.shadow is not None:
        dx, dy, color = params.shadow
        image = _shadow(image, dx, dy, color)
    if params.dx or params.dy:
        image = _shift(image, params.dx, params.dy)
    return image


def refine(
    draw,
    appearance: LineAppearance,
    reference_bgr: np.ndarray,
    cleaned_bgr: np.ndarray,
    polygon: np.ndarray,
    paste,
) -> tuple[np.ndarray, MatchReport]:
    """draw(params) -> RGBA layer. paste(image, layer) -> full BGR image."""
    params = initial_params(appearance)
    best_image = cleaned_bgr
    best_report = MatchReport(0.0, False, 0, {})
    stalled = 0
    for index in range(MAX_PASSES):
        layer = draw(params)
        if layer is None:
            break
        rendered = paste(cleaned_bgr, decorate(layer, params))
        parts = _compare(reference_bgr, rendered, polygon, appearance)
        total = _weighted(parts)
        gated = {name: value for name, value in parts.items() if name != "opacity"}
        accepted = total >= ACCEPT and all(value >= FLOOR for value in gated.values())
        report = MatchReport(total, accepted, index + 1, parts)
        if report.total > best_report.total + 0.004:
            best_image = rendered
            best_report = report
            stalled = 0
        else:
            stalled += 1
        if accepted or stalled >= 2:
            break
        updated = _nudge(params, parts, appearance, reference_bgr, rendered, polygon)
        if updated == params:
            break
        params = updated
    return best_image, best_report


def score_against(
    reference_bgr: np.ndarray,
    rendered_bgr: np.ndarray,
    polygon: np.ndarray,
    appearance: LineAppearance,
) -> MatchReport:
    parts = _compare(reference_bgr, rendered_bgr, polygon, appearance)
    total = _weighted(parts)
    gated = {name: value for name, value in parts.items() if name != "opacity"}
    accepted = total >= ACCEPT and all(value >= FLOOR for value in gated.values())
    return MatchReport(total, accepted, 1, parts)


def _compare(
    reference_bgr: np.ndarray,
    rendered_bgr: np.ndarray,
    polygon: np.ndarray,
    appearance: LineAppearance,
) -> dict[str, float]:
    _mask, original = build_text_mask(reference_bgr, polygon)
    _painted, current = build_text_mask(rendered_bgr, polygon)
    original_stats = _ink_stats(reference_bgr, original)
    current_stats = _ink_stats(rendered_bgr, current)
    if original_stats is None or current_stats is None:
        return {"height": 0.0, "color": 0.0, "weight": 0.0, "tracking": 0.0, "position": 0.0, "opacity": 0.0, "angle": 0.0, "effects": 0.0}
    return {
        "height": _closeness(current_stats["height"], original_stats["height"], tolerance=0.45, absolute=2.0),
        "color": _color_score(current_stats["color"], appearance.color_rgb),
        "weight": _closeness(current_stats["stroke_ratio"], original_stats["stroke_ratio"], tolerance=0.9, absolute=0.04),
        "tracking": _closeness(current_stats["gap_ratio"], original_stats["gap_ratio"], tolerance=1.0, absolute=0.06),
        "position": _position_score(original, current, appearance.align),
        "opacity": _closeness(current_stats["opacity"], original_stats["opacity"], tolerance=1.0, absolute=0.45),
        "angle": _angle_score(polygon, current),
        "effects": _effect_score(rendered_bgr, current, polygon, appearance),
    }


def _nudge(
    params: RenderParams,
    parts: dict[str, float],
    appearance: LineAppearance,
    reference_bgr: np.ndarray,
    rendered_bgr: np.ndarray,
    polygon: np.ndarray,
) -> RenderParams:
    updated = replace(params)
    _mask, original = build_text_mask(reference_bgr, polygon)
    _painted, current = build_text_mask(rendered_bgr, polygon)
    original_stats = _ink_stats(reference_bgr, original)
    current_stats = _ink_stats(rendered_bgr, current)
    if original_stats and current_stats:
        if parts["height"] < 0.9 and current_stats["height"] > 0:
            updated.scale = _clamp(params.scale * original_stats["height"] / current_stats["height"], 0.78, 1.28)
        if parts["tracking"] < 0.86 and current_stats["gap_ratio"] > 0.01:
            updated.tracking = _clamp(params.tracking * appearance.gap_ratio / current_stats["gap_ratio"], 0.45, 1.9)
        if parts["position"] < 0.9:
            shift = _edge_delta(original, current, appearance.align)
            updated.dx = int(np.clip(params.dx + shift[0], -160, 160))
            updated.dy = int(np.clip(params.dy + shift[1], -80, 80))
    if appearance.shadow is not None:
        updated.shadow = appearance.shadow
    if appearance.outline_px:
        updated.outline_px = appearance.outline_px
        updated.outline_rgb = appearance.outline_rgb
    return updated


def _ink_stats(image_bgr: np.ndarray, tight: np.ndarray) -> dict[str, float] | None:
    ys, xs = np.where(tight > 0)
    if xs.size < 8:
        return None
    height = float(ys.max() - ys.min() + 1)
    crop = tight[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    distance = cv2.distanceTransform((crop > 0).astype(np.uint8), cv2.DIST_L2, 3)
    stroke = float(np.median(distance[crop > 0])) * 2.0
    gap_ratio, _space = _spacing_ratios(crop, height)
    color = _median_rgb(image_bgr, tight)
    return {
        "height": height,
        "stroke_ratio": stroke / height,
        "gap_ratio": gap_ratio,
        "color": color,
        "opacity": _opacity(image_bgr, _bbox_polygon(xs, ys), tight),
    }


def _spacing_ratios(crop: np.ndarray, height: float) -> tuple[float, float]:
    occupied = crop.any(axis=0)
    runs: list[tuple[int, int]] = []
    start = 0
    while start < len(occupied):
        end = start + 1
        while end < len(occupied) and occupied[end] == occupied[start]:
            end += 1
        if occupied[start]:
            runs.append((start, end))
        start = end
    if len(runs) < 2 or height <= 0:
        return 0.06, 0.48
    gaps = [runs[index + 1][0] - runs[index][1] for index in range(len(runs) - 1)]
    widths = [end - start for start, end in runs]
    median_width = float(np.median(widths))
    small = [gap for gap in gaps if gap <= max(2.0, median_width * 0.7)]
    large = [gap for gap in gaps if gap > max(2.0, median_width * 0.7)]
    gap_ratio = float(np.median(small)) / height if small else 0.06
    space_ratio = float(np.median(large)) / height if large else 0.48
    return gap_ratio, space_ratio


def _position_score(original: np.ndarray, current: np.ndarray, align: str) -> float:
    original_edge = _anchor(original, align)
    current_edge = _anchor(current, align)
    if original_edge is None or current_edge is None:
        return 0.0
    ys = np.where(original > 0)[0]
    height = max(1.0, float(ys.max() - ys.min() + 1))
    delta = abs(original_edge[0] - current_edge[0]) / height + abs(original_edge[1] - current_edge[1]) / height
    return float(max(0.0, 1.0 - delta / 0.55))


def _anchor(mask: np.ndarray, align: str) -> tuple[float, float] | None:
    ys, xs = np.where(mask > 0)
    if xs.size == 0:
        return None
    y = float(np.median(ys))
    if align == "right":
        return float(xs.max()), y
    if align == "center":
        return float(np.median(xs)), y
    return float(xs.min()), y


def _edge_delta(original: np.ndarray, current: np.ndarray, align: str) -> tuple[int, int]:
    original_edge = _anchor(original, align)
    current_edge = _anchor(current, align)
    if original_edge is None or current_edge is None:
        return 0, 0
    return int(round(original_edge[0] - current_edge[0])), int(round((original_edge[1] - current_edge[1]) * 0.5))


def _placement_offset(tight: np.ndarray, polygon: np.ndarray, align: str) -> tuple[int, int]:
    anchor = _anchor(tight, align)
    points = np.asarray(polygon, dtype=np.float32).reshape(-1, 2)
    if anchor is None or len(points) == 0:
        return 0, 0
    if align == "right":
        target_x = float(points[:, 0].max())
    elif align == "center":
        target_x = float(points[:, 0].mean())
    else:
        target_x = float(points[:, 0].min())
    target_y = float(points[:, 1].min() + points[:, 1].max()) / 2.0
    return int(round(anchor[0] - target_x)), int(round(anchor[1] - target_y))


def _effects(
    image_bgr: np.ndarray,
    tight: np.ndarray,
    polygon: np.ndarray,
) -> tuple[tuple[int, int, tuple[int, int, int]] | None, int, tuple[int, int, int] | None]:
    """A shadow is a translated copy of the ink. An outline is a colored rim.

    Antialiased edges sit on the ink-to-paper line and are not treated as either.
    """
    if int((tight > 0).sum()) < 20:
        return None, 0, None
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    values = gray[tight > 0]
    if values.size < 20 or float(np.percentile(values, 70)) < 35:
        return None, 0, None
    core = (tight > 0) & (gray <= np.percentile(values, 35))
    if int(core.sum()) < 12:
        return None, 0, None
    shape = np.zeros(tight.shape, np.uint8)
    cv2.fillConvexPoly(shape, np.round(np.asarray(polygon)).astype(np.int32), 255)
    paper = np.array(_paper_rgb(image_bgr, shape, tight), np.float32)
    ink = np.array(_median_rgb(image_bgr, core.astype(np.uint8) * 255), np.float32)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    near = cv2.dilate(core.astype(np.uint8) * 255, kernel) > 0
    halo = near & ~core & (shape > 0)
    if int(halo.sum()) < 12:
        return None, 0, None
    rgb = image_bgr[:, :, ::-1].astype(np.float32)
    paper_dist = np.linalg.norm(rgb - paper, axis=2)
    kept = halo & (paper_dist > 28)
    best: tuple[float, int, int] | None = None
    core_u8 = core.astype(np.uint8)
    for dy in range(-8, 9):
        for dx in range(-8, 9):
            if abs(dx) + abs(dy) < 3:
                continue
            shifted = _translate_mask(core_u8, dx, dy)
            overlap = float((shifted & kept).sum()) / float(core.sum())
            if best is None or overlap > best[0]:
                best = (overlap, dx, dy)
    if best is not None and best[0] >= 0.45:
        _score, dx, dy = best
        shifted = _translate_mask(core_u8, dx, dy) & kept
        sampled = image_bgr[shifted > 0][:, ::-1]
        color = tuple(int(channel) for channel in np.median(sampled, axis=0))
        residual = _off_axis(sampled.astype(np.float32), paper, ink)
        if float(sampled.std()) <= 42 and residual < 48:
            return (dx, dy, color), 0, None  # type: ignore[return-value]
        ys = np.where(core)[0]
        text_h = max(8, int(ys.max() - ys.min() + 1))
        return None, max(1, text_h // 18), color  # type: ignore[return-value]
    colors = rgb[kept]
    if colors.size and _off_axis(colors, paper, ink) >= 40:
        sample = image_bgr[kept][:, ::-1]
        color = tuple(int(channel) for channel in np.median(sample, axis=0))
        ys = np.where(core)[0]
        text_h = max(8, int(ys.max() - ys.min() + 1))
        return None, max(1, text_h // 18), color  # type: ignore[return-value]
    return None, 0, None


def _translate_mask(mask: np.ndarray, dx: int, dy: int) -> np.ndarray:
    height, width = mask.shape
    shifted = np.zeros_like(mask)
    src_y = slice(max(0, -dy), height - max(0, dy))
    src_x = slice(max(0, -dx), width - max(0, dx))
    dst_y = slice(max(0, dy), height - max(0, -dy))
    dst_x = slice(max(0, dx), width - max(0, -dx))
    shifted[dst_y, dst_x] = mask[src_y, src_x]
    return shifted


def _off_axis(pixels: np.ndarray, paper: np.ndarray, ink: np.ndarray) -> float:
    axis = ink - paper
    length = float(np.dot(axis, axis))
    if length < 1:
        return 0.0
    offset = pixels - paper
    scale = offset @ axis / length
    projected = paper + scale[:, None] * axis
    return float(np.median(np.linalg.norm(pixels - projected, axis=1)))


def _effect_score(
    rendered_bgr: np.ndarray,
    current: np.ndarray,
    polygon: np.ndarray,
    appearance: LineAppearance,
) -> float:
    shadow, outline_px, _color = _effects(rendered_bgr, current, polygon)
    if appearance.shadow is None and appearance.outline_px == 0:
        return 1.0 if shadow is None and outline_px == 0 else 0.55
    if appearance.shadow is not None:
        if shadow is None:
            return 0.2
        dx = abs(shadow[0] - appearance.shadow[0]) + abs(shadow[1] - appearance.shadow[1])
        return float(max(0.0, 1.0 - dx / 6.0))
    if outline_px == 0:
        return 0.35
    return _closeness(outline_px, appearance.outline_px, tolerance=0.8)


def _angle_score(polygon: np.ndarray, current: np.ndarray) -> float:
    expected = _quad_angle(polygon)
    ys, xs = np.where(current > 0)
    if xs.size < 20:
        return 0.0
    points = np.stack([xs, ys], axis=1).astype(np.float32)
    _center, _size, angle = cv2.minAreaRect(points)
    # minAreaRect angle is the rotation of the rectangle, in a different convention.
    residual = min(abs(expected) % 90, 90 - (abs(expected) % 90))
    fitted = min(abs(angle) % 90, 90 - (abs(angle) % 90))
    return float(max(0.0, 1.0 - abs(residual - fitted) / 18.0))


def _opacity(image_bgr: np.ndarray, polygon: np.ndarray, tight: np.ndarray) -> float:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    ink = gray[tight > 0].astype(np.float32)
    if ink.size == 0:
        return 1.0
    shape = np.zeros(gray.shape, np.uint8)
    cv2.fillConvexPoly(shape, np.round(np.asarray(polygon)).astype(np.int32), 255)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    ring = cv2.subtract(cv2.dilate(shape, kernel), cv2.dilate((tight > 0).astype(np.uint8) * 255, kernel))
    paper = gray[ring > 0].astype(np.float32)
    if paper.size == 0:
        paper = np.array([255.0])
    contrast = abs(float(np.median(paper)) - float(np.median(ink)))
    return float(np.clip(contrast / 140.0, 0.2, 1.0))


def _median_rgb(image_bgr: np.ndarray, mask: np.ndarray) -> tuple[int, int, int]:
    pixels = image_bgr[mask > 0]
    if len(pixels) == 0:
        return (0, 0, 0)
    blue, green, red = np.median(pixels, axis=0)
    return int(red), int(green), int(blue)


def _paper_rgb(image_bgr: np.ndarray, shape: np.ndarray, broad: np.ndarray) -> tuple[int, int, int]:
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    ring = cv2.subtract(cv2.dilate(shape, kernel), broad)
    pixels = image_bgr[ring > 0]
    if len(pixels) == 0:
        return (255, 255, 255)
    blue, green, red = np.median(pixels, axis=0)
    return int(red), int(green), int(blue)


def _quad_angle(polygon: np.ndarray) -> float:
    points = np.asarray(polygon, dtype=np.float32).reshape(-1, 2)
    if len(points) < 2:
        return 0.0
    order = points[np.argsort(points[:, 0])]
    left = order[: min(2, len(order))].mean(axis=0)
    right = order[-min(2, len(order)) :].mean(axis=0)
    vector = right - left
    return float(np.degrees(np.arctan2(vector[1], vector[0])))


def _color_score(found: tuple[int, int, int], expected: tuple[int, int, int]) -> float:
    distance = max(abs(found[channel] - expected[channel]) for channel in range(3))
    return float(max(0.0, 1.0 - distance / 110.0))


def _closeness(found: float, expected: float, tolerance: float = 0.4, absolute: float = 0.0) -> float:
    scale = max(abs(expected) * tolerance, absolute, 1e-3)
    return float(max(0.0, 1.0 - abs(found - expected) / scale))


def _weighted(parts: dict[str, float]) -> float:
    weights = {
        "height": 1.5,
        "color": 1.2,
        "weight": 1.1,
        "tracking": 1.0,
        "position": 0.9,
        "opacity": 0.6,
        "angle": 0.7,
        "effects": 0.7,
    }
    total_weight = sum(weights[name] for name in parts)
    return float(sum(parts[name] * weights[name] for name in parts) / total_weight)


def _dilate_ink(image: np.ndarray, amount: int) -> np.ndarray:
    alpha = image[:, :, 3]
    size = abs(amount) * 2 + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
    if amount > 0:
        grown = cv2.dilate(alpha, kernel)
        color = image.copy()
        color[:, :, 3] = grown
        return color
    shrunk = cv2.erode(alpha, kernel)
    color = image.copy()
    color[:, :, 3] = shrunk
    return color


def _tint(image: np.ndarray, rgb: tuple[int, int, int]) -> np.ndarray:
    colored = image.copy()
    alpha = colored[:, :, 3:4].astype(np.float32) / 255.0
    current = colored[:, :, :3].astype(np.float32)
    target = np.array(rgb, np.float32)
    # Keep the shading already in the patch and shift its average toward the sample.
    opaque = alpha[:, :, 0] > 0.4
    if not np.any(opaque):
        return image
    average = current[opaque].mean(axis=0)
    shift = target - average
    current[opaque] = np.clip(current[opaque] + shift, 0, 255)
    colored[:, :, :3] = current.astype(np.uint8)
    return colored


def _outline(image: np.ndarray, radius: int, rgb: tuple[int, int, int]) -> np.ndarray:
    alpha = image[:, :, 3]
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius * 2 + 1, radius * 2 + 1))
    grown = cv2.dilate(alpha, kernel)
    red, green, blue = rgb
    plate = np.zeros_like(image)
    plate[:, :, 0] = red
    plate[:, :, 1] = green
    plate[:, :, 2] = blue
    plate[:, :, 3] = grown
    cover = alpha.astype(np.float32) / 255.0
    base = plate.astype(np.float32)
    ink = image.astype(np.float32)
    out = base.copy()
    out[:, :, :3] = ink[:, :, :3] * cover[:, :, None] + base[:, :, :3] * (1.0 - cover[:, :, None])
    out[:, :, 3] = np.maximum(grown, alpha)
    return out.astype(np.uint8)


def _shadow(image: np.ndarray, dx: int, dy: int, rgb: tuple[int, int, int]) -> np.ndarray:
    shifted = _shift(image, dx, dy)
    red, green, blue = rgb
    shadow = np.zeros_like(shifted)
    shadow[:, :, 0] = red
    shadow[:, :, 1] = green
    shadow[:, :, 2] = blue
    shadow[:, :, 3] = (shifted[:, :, 3].astype(np.float32) * 0.85).astype(np.uint8)
    return _over(shadow, image)


def _over(base: np.ndarray, ink: np.ndarray) -> np.ndarray:
    if base.shape != ink.shape:
        canvas = np.zeros((max(base.shape[0], ink.shape[0]), max(base.shape[1], ink.shape[1]), 4), np.uint8)
        canvas[: base.shape[0], : base.shape[1]] = base
        base = canvas
        placed = np.zeros_like(base)
        placed[: ink.shape[0], : ink.shape[1]] = ink
        ink = placed
    alpha = ink[:, :, 3:4].astype(np.float32) / 255.0
    mixed = ink[:, :, :3].astype(np.float32) * alpha + base[:, :, :3].astype(np.float32) * (1.0 - alpha)
    out = base.copy()
    out[:, :, :3] = mixed.astype(np.uint8)
    out[:, :, 3] = np.maximum(base[:, :, 3], ink[:, :, 3])
    return out


def _shift(image: np.ndarray, dx: int, dy: int) -> np.ndarray:
    height, width = image.shape[:2]
    canvas = np.zeros((height + abs(dy), width + abs(dx), 4), np.uint8)
    top = max(dy, 0)
    left = max(dx, 0)
    canvas[top : top + height, left : left + width] = image
    return canvas


def _bbox_polygon(xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    return np.array(
        [[xs.min(), ys.min()], [xs.max(), ys.min()], [xs.max(), ys.max()], [xs.min(), ys.max()]],
        np.float32,
    )


def _clamp(value: float, low: float, high: float) -> float:
    return float(min(high, max(low, value)))
