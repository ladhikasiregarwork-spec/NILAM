"""Runtime configuration loaded once from .env at startup.

The orchestrator never calls Azure directly — it only fans out to the four
OCR services over HTTP — so it deliberately does NOT declare the
``AZURE_OPENAI_*`` settings the other services require. (Note: importing
``ocr_match.matcher`` does pull in ``ocr_match.config``, which *does* require
those keys at call time; the shared repo-root .env provides them in real runs.)
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed view of environment variables."""

    # Upstream OCR services (compose overrides these with service-DNS URLs).
    ocr_classifier_url: str = "http://127.0.0.1:8000"
    ocr_sk_url: str = "http://127.0.0.1:8100"
    ocr_slip_url: str = "http://127.0.0.1:8200"
    ocr_mutasi_url: str = "http://127.0.0.1:8300"

    # Service bind.
    app_host: str = "0.0.0.0"
    app_port: int = 8500

    # Timeouts & limits. The mutasi batch LLM parse can take ~30s; keep this
    # generous so a big bundle doesn't trip the upstream timeout.
    upstream_timeout_s: float = 180.0
    max_files: int = 50

    # Income: default analyst bonus-acceptance fraction (0.0 = bonus excluded
    # until an analyst opts in). Clamped to [0, 1] at the API boundary.
    default_bonus_accept_pct: float = 0.0

    # In-memory job store: keep at most this many most-recent jobs.
    job_retention: int = 200

    # Fair-market-value service (standalone; reached over HTTP, not imported —
    # it keeps its own .venv/parquet/models). Default = its uvicorn default port.
    fmv_url: str = "http://127.0.0.1:8000"
    fmv_timeout_s: float = 30.0

    # Decision thresholds.
    max_ltv: float = 0.80   # loan-to-value cap
    max_dsr: float = 0.50   # debt-service-ratio cap (matches the frontend InstallmentCard)
    # Existing monthly installment from SLIK — placeholder until that service is
    # wired. The DSR check subtracts this from the income capacity; 0.0 means
    # "assume no existing debt" for now.
    default_existing_installment: float = 0.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton accessor — read .env once per process."""
    return Settings()  # type: ignore[call-arg]
