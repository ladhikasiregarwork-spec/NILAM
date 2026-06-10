"""Pure mapping between the Azure chat-completions request the NILAM services
send and the body Ollama's OpenAI-compatible endpoint expects. Kept pure so it
is unit-testable without a running Ollama.
"""
from __future__ import annotations

from typing import Any


def resolve_model(deployment: str, model_map: dict[str, str], default_model: str) -> str:
    """Map the Azure 'deployment' name to a local Ollama model."""
    return model_map.get(deployment, default_model)


def prepare_ollama_payload(azure_body: dict[str, Any], model: str) -> dict[str, Any]:
    """Copy the request, point it at the local model, and force non-streaming.

    Ollama's /v1/chat/completions accepts the same shape as Azure/OpenAI
    (messages, temperature, max_tokens, response_format), so this is mostly a
    model-name swap. Returns a new dict — never mutates the caller's body.
    """
    body = dict(azure_body)
    body["model"] = model
    body["stream"] = False
    return body
