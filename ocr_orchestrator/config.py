"""Runtime configuration loaded once from .env at startup.

The orchestrator never calls Azure directly and no longer imports ``ocr_match``;
it fans out to ``ocr_classifier``, ``ocr_sk``, ``ocr_match`` (the slip+mutasi+match
front door) and ``house_fair_market_value`` over HTTP only. It therefore does NOT
declare any ``AZURE_OPENAI_*`` settings.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed view of environment variables."""

    # Upstream OCR services (compose overrides these with service-DNS URLs).
    ocr_classifier_url: str = "http://127.0.0.1:5001"
    ocr_sk_url: str = "http://127.0.0.1:5002"
    # ocr_match is the single front door for slip + mutasi extraction AND matching.
    ocr_match_url: str = "http://127.0.0.1:5005"

    # Service bind.
    app_host: str = "0.0.0.0"
    app_port: int = 8500

    # Timeouts & limits. The mutasi batch LLM parse can take ~30s; keep this
    # generous so a big bundle doesn't trip the upstream timeout.
    upstream_timeout_s: float = 180.0
    # The ocr_match call runs full OCR+LLM on slips + mutasi, so it is the slowest
    # upstream by far; give it its own generous timeout.
    match_timeout_s: float = 300.0
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
