"""LLM adapter settings. Maps the Azure deployment name the services send onto a
local Ollama model, and locates the Ollama server."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    ollama_url: str
    default_model: str
    model_map: dict = field(default_factory=dict)
    timeout_s: float = 300.0


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    default_model = os.environ.get("LLM_ADAPTER_MODEL", "qwen2.5:7b-instruct").strip()
    # The services send AZURE_OPENAI_DEPLOYMENT (default 'gpt-4.1-mini') as the
    # model/deployment name; route whatever they send to the local model.
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini").strip()
    return Settings(
        ollama_url=os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/"),
        default_model=default_model,
        model_map={deployment: default_model},
        timeout_s=float(os.environ.get("LLM_ADAPTER_TIMEOUT_S", "300") or "300"),
    )
