import httpx
import respx
from fastapi.testclient import TestClient

from demo_harness.llm_adapter.app import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# respx.start()/stop() patches httpcore at the process level so the mock is
# visible to the async worker thread that FastAPI's TestClient spawns via anyio.
# The @respx.mock decorator is thread-local and cannot reach that thread.
def test_azure_route_forwards_to_ollama_and_returns_openai_shape():
    respx.start()
    try:
        ollama = respx.post("http://127.0.0.1:11434/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={
                "choices": [{"message": {"role": "assistant", "content": "{\"document_type\":\"slip\"}"}}]
            })
        )
        r = client.post(
            "/openai/deployments/gpt-4.1-mini/chat/completions",
            params={"api-version": "2025-01-01-preview"},
            headers={"api-key": "ignored"},
            json={"messages": [{"role": "user", "content": "classify"}],
                  "response_format": {"type": "json_object"}},
        )
    finally:
        respx.stop()
        respx.reset()

    assert r.status_code == 200
    assert r.json()["choices"][0]["message"]["content"] == "{\"document_type\":\"slip\"}"
    sent = ollama.calls.last.request
    assert b'"model":"qwen2.5:7b-instruct"' in sent.content.replace(b" ", b"")


def test_ollama_unreachable_returns_502_error_body():
    respx.start()
    try:
        respx.post("http://127.0.0.1:11434/v1/chat/completions").mock(
            side_effect=httpx.ConnectError("refused")
        )
        r = client.post(
            "/openai/deployments/gpt-4.1-mini/chat/completions",
            json={"messages": []},
        )
    finally:
        respx.stop()
        respx.reset()

    assert r.status_code == 502
    assert "error" in r.json()
