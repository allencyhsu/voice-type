import json

import responses

from voicetype.memory import CorrectionEntry, CorrectionType
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
def test_polish_forces_traditional_chinese_in_prompt_and_payload():
    responses.post(
        "http://example.test/v1/chat/completions",
        json={
            "choices": [
                {
                    "message": {
                        "content": '{"action":"insert","text":"那規劃的下一步要做什麼呢？"}'
                    }
                }
            ]
        },
        status=200,
    )

    client = QwenClient("http://example.test/v1", "qwen3.6-35b", timeout_sec=5)

    client.polish("那規劃的下一步要做什麼呢?", app_name="Notepad")

    payload = json.loads(responses.calls[0].request.body)
    system_prompt = payload["messages"][0]["content"]
    user_payload = json.loads(payload["messages"][1]["content"])

    assert "Always output Chinese text in Traditional Chinese" in system_prompt
    assert "Convert Simplified Chinese characters to Traditional Chinese" in system_prompt
    assert user_payload["chinese_script"] == "traditional"
    assert user_payload["output_script"] == "traditional"


@responses.activate
def test_polish_prompt_includes_common_voicetype_correction_rules():
    responses.post(
        "http://example.test/v1/chat/completions",
        json={
            "choices": [
                {
                    "message": {
                        "content": '{"action":"insert","text":"檢查 TTS Cache 與 .env。"}'
                    }
                }
            ]
        },
        status=200,
    )

    client = QwenClient("http://example.test/v1", "qwen3.6-35b", timeout_sec=5)

    client.polish("確認一下記錄,有使用到TTS Catch嗎?", app_name="Code")

    payload = json.loads(responses.calls[0].request.body)
    system_prompt = payload["messages"][0]["content"]

    assert "TTS Catch -> TTS Cache" in system_prompt
    assert "點emv -> .env" in system_prompt
    assert "Quizper -> Whisper" in system_prompt
    assert "Hot War -> hotword" in system_prompt
    assert "Do not translate English product names, menu item names, filenames, or code terms" in system_prompt


@responses.activate
def test_polish_fails_open_to_raw_text_on_server_error():
    responses.post("http://example.test/v1/chat/completions", status=500)
    client = QwenClient("http://example.test/v1", "qwen3.6-35b", timeout_sec=5)

    assert client.polish("raw text", app_name="Notepad") == "raw text"


@responses.activate
def test_polish_sends_correction_memory_in_user_payload():
    responses.post(
        "http://example.test/v1/chat/completions",
        json={"choices": [{"message": {"content": '{"action":"insert","text":"Qwen is ready."}'}}]},
        status=200,
    )
    memory = [
        CorrectionEntry(
            id="entry-1",
            type=CorrectionType.TERM,
            wrong="cue and",
            correct="Qwen",
            scope="global",
            created_at="2026-05-19T10:00:00+08:00",
            updated_at="2026-05-19T10:00:00+08:00",
            uses=0,
        )
    ]
    client = QwenClient("http://example.test/v1", "qwen3.6-35b", timeout_sec=5)

    client.polish("cue and is ready", app_name="Notepad", correction_memory=memory)

    payload = json.loads(responses.calls[0].request.body)
    user_payload = json.loads(payload["messages"][1]["content"])
    assert user_payload["correction_memory"] == [
        {"id": "entry-1", "type": "term", "wrong": "cue and", "correct": "Qwen"}
    ]
