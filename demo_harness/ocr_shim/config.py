"""OCR shim settings, read from the environment (so .env / start script can tune)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    enable_tesseract: bool
    min_chars: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        enable_tesseract=os.environ.get("OCR_SHIM_TESSERACT", "false").strip().lower() == "true",
        # `or "10"` guards an empty-string override (OCR_SHIM_MIN_CHARS=), which
        # would otherwise crash int("").
        min_chars=int(os.environ.get("OCR_SHIM_MIN_CHARS", "10") or "10"),
    )
