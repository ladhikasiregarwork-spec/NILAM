"""Azure-OpenAI stand-in: serves the `/openai/deployments/{deployment}/chat/completions`
route the NILAM services build, forwarding to a local Ollama OpenAI-compatible
endpoint. Configured via AZURE_OPENAI_ENDPOINT pointing here; no code changes to
the services.
"""
from __future__ import annotations

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import translate as T
from .config import get_settings

app = FastAPI(title="LLM adapter (Azure-OpenAI stand-in)")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "llm-adapter"}


@app.post("/openai/deployments/{deployment}/chat/completions")
async def chat_completions(deployment: str, request: Request) -> JSONResponse:
    settings = get_settings()
    azure_body = await request.json()
    model = T.resolve_model(deployment, settings.model_map, settings.default_model)
    payload = T.prepare_ollama_payload(azure_body, model)
    try:
        async with httpx.AsyncClient(timeout=settings.timeout_s) as client:
            resp = await client.post(f"{settings.ollama_url}/v1/chat/completions", json=payload)
    except httpx.HTTPError as exc:
        return JSONResponse(
            {"error": {"message": f"ollama unreachable: {exc}", "type": "upstream_error"}},
            status_code=502,
        )
    return JSONResponse(resp.json(), status_code=resp.status_code)
