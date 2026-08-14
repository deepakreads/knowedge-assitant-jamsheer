import httpx
import pytest

from app.services import ollama_service


def test_extract_json_plain():
    assert ollama_service.extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_with_markdown_fence():
    raw = "Here is the result:\n```json\n{\"a\": 1, \"b\": [1,2,3]}\n```\nThanks!"
    assert ollama_service.extract_json(raw) == {"a": 1, "b": [1, 2, 3]}


def test_extract_json_with_surrounding_text():
    raw = 'Sure, here you go: {"a": 1} -- let me know if you need more.'
    assert ollama_service.extract_json(raw) == {"a": 1}


def test_extract_json_array():
    raw = "```\n[{\"x\": 1}, {\"x\": 2}]\n```"
    assert ollama_service.extract_json(raw) == [{"x": 1}, {"x": 2}]


def test_extract_json_invalid_returns_none():
    assert ollama_service.extract_json("not json at all") is None
    assert ollama_service.extract_json("") is None


def test_generate_retries_then_raises(monkeypatch):
    """If Ollama is unreachable, generate() should retry then raise OllamaError."""
    call_count = {"n": 0}

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            call_count["n"] += 1
            raise httpx.ConnectError("connection refused", request=None)

    monkeypatch.setattr(ollama_service, "_client", lambda: FakeClient())
    monkeypatch.setattr(ollama_service, "OLLAMA_MAX_RETRIES", 2)

    with pytest.raises(ollama_service.OllamaError):
        ollama_service.generate(model="qwen2.5:7b", prompt="hello")

    assert call_count["n"] == 3  # initial attempt + 2 retries


def test_generate_succeeds(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": "hello world"}

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(ollama_service, "_client", lambda: FakeClient())

    result = ollama_service.generate(model="qwen2.5:7b", prompt="hello")
    assert result == "hello world"
