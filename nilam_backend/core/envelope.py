from typing import Any


def ok(**fields: Any) -> dict:
    """Success envelope: {"ok": True, ...fields}."""
    return {"ok": True, **fields}


def err(error: str, raw: Any = None) -> dict:
    """Failure envelope: {"ok": False, "error": ..., "raw"?: ...}."""
    body: dict = {"ok": False, "error": error}
    if raw is not None:
        body["raw"] = raw
    return body
