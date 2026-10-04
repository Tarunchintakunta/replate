"""Bundled OFL faces. Image lines pick the closest one; the source file is not recovered."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from app.config import get_settings

_FILES = {
    ("sans", False): "LiberationSans-Regular.ttf",
    ("sans", True): "LiberationSans-Bold.ttf",
    ("serif", False): "LiberationSerif-Regular.ttf",
    ("serif", True): "LiberationSerif-Bold.ttf",
    ("mono", False): "LiberationMono-Regular.ttf",
    ("mono", True): "LiberationMono-Bold.ttf",
    ("condensed", False): "BarlowCondensed-Regular.ttf",
    ("condensed", True): "BarlowCondensed-Bold.ttf",
    ("receipt", False): "ShareTechMono-Regular.ttf",
    ("receipt", True): "ShareTechMono-Regular.ttf",
}


def resolve_font(family: str, bold: bool) -> Path | None:
    known = {"sans", "serif", "mono", "condensed", "receipt"}
    key = (family if family in known else "sans", bool(bold))
    path = get_settings().fonts_dir / _FILES[key]
    if path.is_file():
        return path
    fallback = get_settings().fonts_dir / _FILES[("sans", False)]
    return fallback if fallback.is_file() else None


def fonts_available() -> bool:
    return resolve_font("sans", False) is not None


def font_key(name: str) -> str:
    """'ABCDEF+TimesNewRomanPS-BoldMT' and 'Times New Roman Bold' -> 'timesnewromanbold'."""
    parts = re.split(r"[-,\s]+", name.split("+")[-1])
    parts = [re.sub(r"(psmt|ps|mt)$", "", p.lower()) for p in parts if p.lower() != "regular"]
    return "".join(re.sub(r"[^a-z0-9]", "", p) for p in parts)


@lru_cache(maxsize=1)
def _installed() -> dict[str, Path]:
    import fitz

    roots = [get_settings().fonts_dir, Path("/System/Library/Fonts"), Path("/Library/Fonts"), Path.home() / "Library/Fonts", Path("/usr/share/fonts"), Path.home() / ".fonts", Path("C:/Windows/Fonts"), get_settings().models_dir / "font-library"]
    found: dict[str, Path] = {}
    for root in roots:
        for path in sorted(root.rglob("*")) if root.is_dir() else []:
            if path.suffix.lower() not in (".ttf", ".otf"):  # ponytail: .ttc faces skipped
                continue
            try:
                found.setdefault(font_key(fitz.Font(fontfile=str(path)).name), path)
            except Exception:  # noqa: BLE001 - unreadable font file
                continue
    return found


def installed_font(pdf_font_name: str) -> Path | None:
    """The real font file for a PDF base font name, when this machine has it."""
    return _installed().get(font_key(pdf_font_name))


def family_from_pdf(flags: int, font_name: str) -> tuple[str, bool]:
    name = (font_name or "").lower()
    bold = bool(flags & 16) or any(token in name for token in ("bold", "black", "heavy"))
    if any(token in name for token in ("arial", "helvetica", "tahoma", "verdana", "calibri", "segoe", "sans", "gothic")):
        family = "sans"  # producers often set the serif flag wrongly; the name wins
    elif flags & 8 or any(token in name for token in ("courier", "mono", "consolas", "menlo", "liberationmono")):
        family = "mono"
    elif flags & 4 or any(token in name for token in ("times", "serif", "georgia", "roman", "cambria", "liberationserif")):
        family = "serif"
    else:
        family = "sans"
    return family, bold
