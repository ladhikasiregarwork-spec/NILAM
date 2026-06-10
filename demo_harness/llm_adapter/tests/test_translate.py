from demo_harness.llm_adapter import translate as T


def test_resolve_model_uses_map_then_default():
    model_map = {"gpt-4.1-mini": "qwen2.5:7b-instruct"}
    assert T.resolve_model("gpt-4.1-mini", model_map, "fallback") == "qwen2.5:7b-instruct"
    assert T.resolve_model("unknown-deploy", model_map, "fallback") == "fallback"


def test_prepare_ollama_payload_sets_model_and_disables_stream():
    azure_body = {
        "messages": [{"role": "user", "content": "hi"}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    out = T.prepare_ollama_payload(azure_body, "qwen2.5:7b-instruct")
    assert out["model"] == "qwen2.5:7b-instruct"
    assert out["stream"] is False
    assert out["response_format"] == {"type": "json_object"}
    assert azure_body is not out
