"""Thin async HTTP client for the upstream OCR / NPW services.

Wraps httpx with a shared timeout and a single `UpstreamError`, so callers
(orchestration) can mark a stage `error` and degrade gracefully rather than
surface a 500 (design spec §7: upstream failures degrade, not 500).
"""

from typing import Any, Optional

import httpx

DEFAULT_TIMEOUT = 30.0


class UpstreamError(Exception):
    """Raised when an upstream service is unreachable or returns an error status."""

    def __init__(self, service: str, detail: str):
        super().__init__("{}: {}".format(service, detail))
        self.service = service
        self.detail = detail


async def post_json(url: str, json: Any, timeout: float = DEFAULT_TIMEOUT, service: str = "upstream") -> Any:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=json)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        raise UpstreamError(service, str(e))


async def post_files(
    url: str,
    files: Any,
    data: Optional[dict] = None,
    timeout: float = DEFAULT_TIMEOUT,
    service: str = "upstream",
) -> Any:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, files=files, data=data)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        raise UpstreamError(service, str(e))


async def get_json(
    url: str,
    params: Optional[dict] = None,
    timeout: float = DEFAULT_TIMEOUT,
    service: str = "upstream",
) -> Any:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        raise UpstreamError(service, str(e))
