"""Runtime configuration.

Environment variables use the ``REWORDS_`` prefix, for example
``REWORDS_MAX_UPLOAD_BYTES=10485760``.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Secrets such as FAL_KEY live in the untracked project .env. Real environment
# variables win over it.
try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env", override=False)
except ImportError:  # pragma: no cover - optional
    pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REWORDS_", extra="ignore")

    storage_dir: Path = PROJECT_ROOT / "storage"
    models_dir: Path = PROJECT_ROOT / "models"
    fonts_dir: Path = PROJECT_ROOT / "fonts"
    max_upload_bytes: int = 25 * 1024 * 1024
    max_pdf_pages: int = 30
    max_page_pixels: int = 16_000_000
    ocr_lang: str = "en"
    render_dpi: int = 144
    cleanup_hours: int = 24
    lama_relpath: str = "lama/big-lama.pt"
    # "auto": lines that need letters the page does not have go to fal.ai. "off": never sent.
    text_edit: str = "auto"
    cors_origins: str = "http://127.0.0.1:8742,http://localhost:8742"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def cors_allow_all(self) -> bool:
        return "*" in self.cors_origin_list

    @property
    def lama_path(self) -> Path:
        return self.models_dir / self.lama_relpath


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings() -> None:
    get_settings.cache_clear()


def apply_model_env(settings: Settings) -> None:
    """Point PaddleX caches at the project models directory before import."""
    cache = settings.models_dir / "paddlex"
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(cache))
    os.environ.setdefault("PADDLEX_HOME", str(cache))
    # OneDNN on some CPU wheels crashes or hangs during OCR. CPU math is enough.
    os.environ.setdefault("FLAGS_use_mkldnn", "0")
    # PaddleX reads this name. The log line mentions a shorter alias; that alias is not what the code checks.
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
