"""Neural text edit through OpenAI (gpt-image edit) or fal.ai (Qwen-Image-Edit inpaint).

Used for lines the page-letter path cannot carry: letters that are not on
the page, light-on-dark or glowing text, painted or outlined faces, and lines
that do not cut into letters. Only a crop around the line and a mask of the
changed letters are sent. The result is pasted back inside that mask, so
pixels outside it are the original ones.

Candidates are checked with OCR; one that does not read as the new text is
discarded rather than shown.
"""

from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass
from difflib import SequenceMatcher

import cv2
import numpy as np

from app.errors import AppError

logger = logging.getLogger(__name__)

ENDPOINT = "fal-ai/qwen-image-edit/inpaint"
# The model works near 1 MP; small receipt text must be enlarged to be redrawn.
_MAX_PIXELS = 1_048_576
_MIN_TEXT_PX = 64


@dataclass
class TextEditResult:
    image: np.ndarray
    read_as: str
    candidates: int


def fal_key_present() -> bool:
    return bool(os.environ.get("FAL_KEY", "").strip())


def openai_key_present() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())


def key_present() -> bool:
    return openai_key_present() or fal_key_present()


def engine() -> str:
    return "openai" if openai_key_present() else "fal" if fal_key_present() else "none"


def status() -> dict:
    return {"engine": engine(), "key": key_present()}


def edit_line(
    working_bgr: np.ndarray,
    polygon: np.ndarray,
    change_mask: np.ndarray,
    old_text: str,
    new_text: str,
    read_text,
    *,
    num_images: int = 2,
) -> TextEditResult:
    """change_mask: page-size uint8, 255 where letters may be redrawn."""
    if not key_present():
        raise AppError(
            "TEXT_EDIT_KEY_MISSING",
            "No OPENAI_API_KEY or FAL_KEY is set, so the AI text edit was not sent.",
            503,
        )
    x0, y0, x1, y1 = _context_box(working_bgr.shape[:2], polygon, change_mask)
    crop = working_bgr[y0:y1, x0:x1]
    mask = change_mask[y0:y1, x0:x1]
    scale = _scale_for(crop, polygon)
    big = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA)
    big_mask = cv2.resize(mask, (big.shape[1], big.shape[0]), interpolation=cv2.INTER_NEAREST)
    prompt = (
        f'Replace the text "{old_text}" with "{new_text}". '
        f'Spell it exactly: {" ".join(new_text)}. '
        "Keep exactly the same font, letter shapes, stroke weight, size, letter spacing, colour, "
        "outline, shadow, glow, texture, blur and perspective as the surrounding text. "
        "Keep the background unchanged. Change nothing else."
    )
    if openai_key_present():
        decoded_images = _openai_edit(big, big_mask, prompt, num_images)
    else:
        decoded_images = _fal_edit(big, big_mask, prompt, num_images)

    feather = cv2.GaussianBlur(cv2.dilate(mask, np.ones((3, 3), np.uint8)).astype(np.float32) / 255.0, (0, 0), 1.2)
    best: tuple[float, np.ndarray, str] | None = None
    for decoded in decoded_images:
        small = cv2.resize(decoded, (crop.shape[1], crop.shape[0]), interpolation=cv2.INTER_AREA)
        merged = (crop * (1 - feather[..., None]) + small * feather[..., None]).astype(np.uint8)
        if _runs_past_mask(crop, small, mask):
            logger.info("AI candidate rejected: its letters run past the editable area")
            continue
        page = working_bgr.copy()
        page[y0:y1, x0:x1] = merged
        read = read_text(page, polygon, change_mask)
        score = SequenceMatcher(a=_norm(read), b=_norm(new_text)).ratio()
        logger.info("AI candidate read %r (%.2f)", read, score)
        if best is None or score > best[0]:
            best = (score, page, read)
    if best is None:
        raise AppError("TEXT_EDIT_FAILED", "The AI text edit returned no image.", 502)
    if best[0] < 0.8:
        raise AppError(
            "TEXT_EDIT_MISSPELLED",
            f'The AI text edit did not spell "{new_text}" (read "{best[2]}"). Nothing was changed; try again.',
            422,
        )
    return TextEditResult(best[1], best[2], len(decoded_images))


def _fal_edit(big: np.ndarray, big_mask: np.ndarray, prompt: str, num_images: int) -> list[np.ndarray]:
    try:
        import fal_client
    except Exception as exc:  # noqa: BLE001
        raise AppError("TEXT_EDIT_UNAVAILABLE", "fal-client is not installed (pip install fal-client).", 503) from exc
    try:
        result = fal_client.subscribe(
            ENDPOINT,
            arguments={
                "prompt": prompt,
                "image_url": _data_uri(big),
                "mask_url": _data_uri(cv2.cvtColor(big_mask, cv2.COLOR_GRAY2BGR)),
                "num_images": num_images,
                "num_inference_steps": 30,
                "guidance_scale": 4,
                "strength": 0.93,
                "output_format": "png",
                "sync_mode": True,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("fal.ai text edit failed: %s", exc)
        raise AppError("TEXT_EDIT_FAILED", f"The AI text edit request failed: {exc}", 502) from exc
    found = [_decode(item.get("url", "")) for item in result.get("images") or []]
    return [image for image in found if image is not None]


# gpt-image accepts these output sizes; the crop is padded to the nearest shape
# so the result maps back without stretching.
_OPENAI_SIZES = {(1024, 1024): "1024x1024", (1536, 1024): "1536x1024", (1024, 1536): "1024x1536"}


def _openai_edit(big: np.ndarray, big_mask: np.ndarray, prompt: str, num_images: int) -> list[np.ndarray]:
    try:
        from openai import BadRequestError, OpenAI
    except Exception as exc:  # noqa: BLE001
        raise AppError("TEXT_EDIT_UNAVAILABLE", "The openai package is not installed (pip install openai).", 503) from exc
    h, w = big.shape[:2]
    (out_w, out_h), size = min(_OPENAI_SIZES.items(), key=lambda kv: abs(np.log((kv[0][0] / kv[0][1]) / (w / h))))
    # Pad (not stretch) to the output aspect, then scale to the exact output size.
    pad_w = max(w, int(round(h * out_w / out_h)))
    pad_h = max(h, int(round(w * out_h / out_w)))
    left, top = (pad_w - w) // 2, (pad_h - h) // 2
    image = cv2.copyMakeBorder(big, top, pad_h - h - top, left, pad_w - w - left, cv2.BORDER_REPLICATE)
    mask = cv2.copyMakeBorder(big_mask, top, pad_h - h - top, left, pad_w - w - left, cv2.BORDER_CONSTANT, value=0)
    image = cv2.resize(image, (out_w, out_h), interpolation=cv2.INTER_AREA)
    mask = cv2.resize(mask, (out_w, out_h), interpolation=cv2.INTER_NEAREST)
    # OpenAI masks: transparent pixels are the ones that may change.
    rgba = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
    rgba[:, :, 3] = np.where(mask > 0, 0, 255).astype(np.uint8)
    ok_i, image_png = cv2.imencode(".png", image)
    ok_m, mask_png = cv2.imencode(".png", rgba)
    if not ok_i or not ok_m:
        raise AppError("TEXT_EDIT_FAILED", "Could not encode the crop.", 500)
    client = OpenAI()
    model = os.environ.get("OPENAI_IMAGE_MODEL") or _openai_model(client)
    args = dict(
        model=model,
        image=("line.png", image_png.tobytes(), "image/png"),
        mask=("mask.png", mask_png.tobytes(), "image/png"),
        prompt=prompt,
        n=num_images,
        size=size,
        quality=os.environ.get("OPENAI_IMAGE_QUALITY", "high"),
        input_fidelity="high",
    )
    try:
        try:
            response = client.images.edit(**args)
        except (BadRequestError, TypeError) as exc:
            if "input_fidelity" not in str(exc):
                raise
            args.pop("input_fidelity")
            response = client.images.edit(**args)
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("OpenAI image edit failed: %s", exc)
        raise AppError("TEXT_EDIT_FAILED", f"The AI text edit request failed: {exc}", 502) from exc
    results = []
    for item in response.data or []:
        if not item.b64_json:
            continue
        decoded = cv2.imdecode(np.frombuffer(base64.b64decode(item.b64_json), np.uint8), cv2.IMREAD_COLOR)
        if decoded is None:
            continue
        back = cv2.resize(decoded, (pad_w, pad_h), interpolation=cv2.INTER_CUBIC)
        results.append(back[top : top + h, left : left + w])
    logger.info("OpenAI %s returned %d image(s)", model, len(results))
    return results


# Picked by a visual test on real photos (serif sign, neon, blurry receipt):
# 2.5-sunburst kept face, weight and texture best and was fastest (~30 s).
_PREFERRED = ("gpt-image-2.5-sunburst", "gpt-image-2", "gpt-image-1.5", "gpt-image-1")


def _openai_model(client) -> str:
    try:
        names = {m.id for m in client.models.list()}
    except Exception:  # noqa: BLE001
        return _PREFERRED[0]
    return next((name for name in _PREFERRED if name in names), _PREFERRED[-1])


def _runs_past_mask(crop: np.ndarray, result: np.ndarray, mask: np.ndarray) -> bool:
    """A letter cut by the mask edge: just outside it, the model's image differs strongly from the original."""
    inside = mask > 0
    ring = cv2.dilate(mask, np.ones((9, 9), np.uint8)) > 0
    ring &= ~cv2.dilate(mask, np.ones((3, 3), np.uint8)).astype(bool)
    if int(ring.sum()) < 20 or not inside.any():
        return False
    diff = np.abs(crop.astype(np.int16) - result.astype(np.int16)).max(axis=2)
    # Models shift colours slightly everywhere; a cut letter shows as a band of large change.
    return float((diff[ring] > 60).mean()) > 0.08


def _norm(text: str) -> str:
    return " ".join(text.upper().split())


def _context_box(page_shape, polygon: np.ndarray, mask: np.ndarray) -> tuple[int, int, int, int]:
    points = np.asarray(polygon, np.float32).reshape(-1, 2)
    ys, xs = np.where(mask > 0)
    left = min(points[:, 0].min(), xs.min() if xs.size else points[:, 0].min())
    right = max(points[:, 0].max(), xs.max() if xs.size else points[:, 0].max())
    top = min(points[:, 1].min(), ys.min() if ys.size else points[:, 1].min())
    bottom = max(points[:, 1].max(), ys.max() if ys.size else points[:, 1].max())
    h = bottom - top
    # Room for the model to see the face and the surface it sits on.
    x0 = int(max(0, left - 1.0 * h))
    x1 = int(min(page_shape[1], right + 1.0 * h))
    y0 = int(max(0, top - 0.8 * h))
    y1 = int(min(page_shape[0], bottom + 0.8 * h))
    return x0, y0, x1, y1


def _scale_for(crop: np.ndarray, polygon: np.ndarray) -> float:
    points = np.asarray(polygon, np.float32).reshape(-1, 2)
    text_h = max(1.0, float(points[:, 1].max() - points[:, 1].min()))
    up = max(1.0, _MIN_TEXT_PX / text_h)
    area = crop.shape[0] * crop.shape[1] * up * up
    if area > _MAX_PIXELS:
        up *= (_MAX_PIXELS / area) ** 0.5
    return up


def _data_uri(image_bgr: np.ndarray) -> str:
    ok, buffer = cv2.imencode(".png", image_bgr)
    if not ok:
        raise AppError("TEXT_EDIT_FAILED", "Could not encode the crop.", 500)
    return "data:image/png;base64," + base64.b64encode(buffer.tobytes()).decode("ascii")


def _decode(url: str) -> np.ndarray | None:
    if url.startswith("data:"):
        data = base64.b64decode(url.split(",", 1)[1])
    elif url.startswith("http"):
        import httpx

        data = httpx.get(url, timeout=60).content
    else:
        return None
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    return image


def line_mask(page_shape, polygon: np.ndarray, old_text: str, new_text: str) -> np.ndarray:
    """The whole line, grown along its baseline when the new text is longer."""
    points = np.asarray(polygon, np.float32).reshape(-1, 2)
    if len(points) == 4:
        tl, tr, br, bl = _order(points)
        growth = max(0.0, (len(new_text) - len(old_text)) / max(len(old_text), 1)) + 0.15
        tr = tr + (tr - tl) * growth
        br = br + (br - bl) * growth
        points = np.float32([tl, tr, br, bl])
    mask = np.zeros(page_shape, np.uint8)
    cv2.fillPoly(mask, [np.round(points).astype(np.int32)], 255)
    h = float(points[:, 1].max() - points[:, 1].min())
    k = max(3, int(h * 0.12) | 1)
    return cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))


def _order(points: np.ndarray) -> np.ndarray:
    s, d = points.sum(axis=1), np.diff(points, axis=1).ravel()
    return np.float32([points[np.argmin(s)], points[np.argmin(d)], points[np.argmax(s)], points[np.argmax(d)]])
