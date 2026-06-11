"""Async httpx clients for the orchestrator's upstreams.

The orchestrator parses no PDFs itself: ``ocr_match`` is the single front door for
slip + mutasi extraction AND matching, ``ocr_classifier`` labels docs, ``ocr_sk``
parses employment letters, and ``house_fair_market_value`` prices collateral. Each
function takes already-read ``(filename, bytes)`` tuples (or a JSON body) and
returns the loosely-typed JSON the pipeline consumes.
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
    except httpx.TransportError as exc:
        # TransportError is the base of ConnectError and all timeout/network errors,
        # so a slow or down upstream becomes a clean UpstreamUnreachableError rather
        # than escaping and leaving the orchestration job stuck.
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


async def match_documents(
    slip_pdfs: list[tuple[str, bytes]],
    mutasi_pdfs: list[tuple[str, bytes]],
    *,
    password: str | None = None,
) -> dict[str, Any]:
    """POST slip + mutasi PDFs to ocr_match:/api/v1/match. Returns the full
    MatchResponse JSON: ``matches``, ``slip_extraction`` (full ocr_slip body),
    ``mutasi_extraction`` (full ocr_mutasi body, all categories), ``audit``.

    The single orchestrator ``password`` is forwarded as both ``slip_password`` and
    ``mutation_password`` (ocr_match takes them separately)."""
    s = get_settings()
    url = f"{s.ocr_match_url}/api/v1/match"
    files = (
        [("slips", (name, data, "application/pdf")) for name, data in slip_pdfs]
        + [("mutations", (name, data, "application/pdf")) for name, data in mutasi_pdfs]
    )
    data: dict[str, str] = {}
    if password:
        data["slip_password"] = password
        data["mutation_password"] = password
    try:
        async with httpx.AsyncClient(timeout=s.match_timeout_s) as client:
            r = await client.post(url, files=files, data=data)
    except httpx.TransportError as exc:
        raise UpstreamUnreachableError(
            f"ocr_match not reachable at {url}: {exc}"
        ) from exc
    if r.status_code >= 400:
        raise UpstreamHttpError("ocr_match", r.status_code, r.text)
    return r.json()


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


async def predict_fair_value(collateral: dict[str, Any]) -> dict[str, Any]:
    """POST collateral to house_fair_market_value:/predict (JSON body, not
    multipart). Returns the FMV response dict: ``land_value``, ``building_value``,
    ``fair_value``, ``location_matched``, ``backend``, ``warnings``.

    Mirrors the error semantics of ``_post``: a transport/network error becomes
    ``UpstreamUnreachableError`` and a 4xx/5xx becomes ``UpstreamHttpError`` so
    the pipeline's fmv stage can degrade cleanly."""
    s = get_settings()
    url = f"{s.fmv_url}/predict"
    try:
        async with httpx.AsyncClient(timeout=s.fmv_timeout_s) as client:
            r = await client.post(url, json=collateral)
    except httpx.TransportError as exc:
        raise UpstreamUnreachableError(
            f"house_fair_market_value not reachable at {url}: {exc}"
        ) from exc
    if r.status_code >= 400:
        raise UpstreamHttpError("house_fair_market_value", r.status_code, r.text)
    return r.json()
