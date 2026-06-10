"""Async httpx clients for the four OCR services.

Each function takes already-read ``(filename, bytes)`` tuples and returns the
loosely-typed JSON the orchestrator pipeline consumes. We never re-parse PDFs
here; the services own all PDF/OCR I/O.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import get_settings

logger = logging.getLogger(__name__)


class UpstreamUnreachableError(RuntimeError):
    """The upstream service refused the connection (network/DNS error)."""


class UpstreamHttpError(RuntimeError):
    """The upstream service answered with a 4xx/5xx response."""

    def __init__(self, service: str, status_code: int, body: str) -> None:
        super().__init__(f"{service} returned {status_code}: {body[:300]}")
        self.service = service
        self.status_code = status_code
        self.body = body


def _files(pdfs: list[tuple[str, bytes]]) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("files", (name, data, "application/pdf")) for name, data in pdfs]


async def _post(service: str, url: str, *, files, data=None, params=None) -> dict[str, Any]:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=settings.upstream_timeout_s) as client:
            r = await client.post(url, files=files, data=data or {}, params=params or {})
    except httpx.ConnectError as exc:
        raise UpstreamUnreachableError(f"{service} not reachable at {url}: {exc}") from exc
    if r.status_code >= 400:
        raise UpstreamHttpError(service, r.status_code, r.text)
    return r.json()


async def classify_documents(pdfs: list[tuple[str, bytes]]) -> list[dict[str, Any]]:
    """POST every file to ocr_classifier:/classify-batch. Returns ``results[]``
    (one dict per file: ``filename``, ``document_type``, ``confidence``, ...)."""
    s = get_settings()
    payload = await _post(
        "ocr_classifier", f"{s.ocr_classifier_url}/classify-batch", files=_files(pdfs)
    )
    return payload.get("results", [])


async def parse_slips(
    pdfs: list[tuple[str, bytes]], password: str | None = None
) -> list[dict[str, Any]]:
    """POST slips to ocr_slip:/parse. Returns ``documents[]`` (English-keyed
    per-slip dicts: ``worker_name``, ``total_paid``, ``period``, ...)."""
    s = get_settings()
    data = {"password": password} if password else {}
    payload = await _post(
        "ocr_slip", f"{s.ocr_slip_url}/parse",
        files=_files(pdfs), data=data, params={"ocr": "auto"},
    )
    return payload.get("documents", [])


async def extract_mutations(
    pdfs: list[tuple[str, bytes]], password: str | None = None
) -> dict[str, Any]:
    """POST bank statements to ocr_mutasi:/extract-batch. Returns the FULL batch
    payload (``files[]``, ``credits[]`` across all categories, ``audit``).

    Unlike ocr_match (Gaji-only), the orchestrator needs every category for the
    income formula, plus ``files[].account.nama`` for applicant-name fallback."""
    s = get_settings()
    data = {"password": password} if password else {}
    return await _post(
        "ocr_mutasi", f"{s.ocr_mutasi_url}/api/v1/mutations/extract-batch",
        files=_files(pdfs), data=data, params={"classify": "true"},
    )


async def parse_sk(
    pdfs: list[tuple[str, bytes]], password: str | None = None
) -> dict[str, Any]:
    """POST employment letters to ocr_sk:/parse. Returns the raw response
    (``summary``, ``extracted``, ...)."""
    s = get_settings()
    data = {"password": password} if password else {}
    return await _post(
        "ocr_sk", f"{s.ocr_sk_url}/parse", files=_files(pdfs), data=data
    )
