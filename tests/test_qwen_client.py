import json

import responses

from voicetype.qwen_client import QwenClient


@responses.activate
def test_health_uses_chat_completions_preflight():
    responses.post(
        "http://example.test/v1/chat/completions",
        json={
            "choices": [
                {
                    "message": {
                        "content": '{"action":"insert","text":"ok"}'
                    }
                }
            ]
        },
        status=200,
    )

    client = QwenClient("http://example.test/v1", "qwen3.6-35b", timeout_sec=5)

    assert client.health() == {
        "status": "available",
        "endpoint": "http://example.test/v1/chat/completions",
        "model": "qwen3.6-35b",
    }


@responses.activate
def test_polish_returns_text_from_json_response():
    responses.post(
        "http://example.test/v1/chat/completions",
        json={
            "choices": [
                {
                    "message": {
                        "content": '{"action":"insert","text":"Clean final text."}'
                    }
                }
            ]
        },
        status=200,
    )

    client = QwenClient("http://example.test/v1", "qwen3.6-35b", timeout_sec=5)

    assert client.polish("clean final text", app_name="Notepad") == "Clean final text."


@responses.activate
def test_polish_sends_hotwords_in_user_payload():
    responses.post(
        "http://example.test/v1/chat/completions",
        json={
            "choices": [
                {
                    "message": {
                        "content": '{"action":"insert","text":"Clean final text."}'
                    }
                }
            ]
        },
        status=200,
    )

    client = QwenClient("http://example.test/v1", "qwen3.6-35b", timeout_sec=5)

    client.polish("clean final text", app_name="Notepad", hotwords=["Typeless", "Faster Whisper"])

    payload = json.loads(responses.calls[0].request.body)
    user_payload = json.loads(payload["messages"][1]["content"])
    assert user_payload["hotwords"] == ["Typeless", "Faster Whisper"]


@responses.activate
def test_polish_fails_open_to_raw_text_on_server_error():
    responses.post("http://example.test/v1/chat/completions", status=500)
    client = QwenClient("http://example.test/v1", "qwen3.6-35b", timeout_sec=5)

    assert client.polish("raw text", app_name="Notepad") == "raw text"
