from pathlib import Path

import responses

from voicetype.whisper_client import WhisperClient, TranscriptionSegment


@responses.activate
def test_health_returns_server_json():
    responses.get(
        "http://example.test/health",
        json={"status": "healthy", "model": "large-v2"},
        status=200,
    )

    client = WhisperClient("http://example.test", timeout_sec=5)

    assert client.health() == {"status": "healthy", "model": "large-v2"}


@responses.activate
def test_transcribe_posts_audio_and_parses_segments(tmp_path):
    wav_path = tmp_path / "sample.wav"
    wav_path.write_bytes(b"fake wav")
    responses.post(
        "http://example.test/transcribe",
        json={
            "success": True,
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "hello"},
                {"start": 1.0, "end": 2.0, "text": " world"},
            ],
            "language": "en",
            "language_probability": 0.99,
            "duration": 2.0,
            "transcribe_time": 0.5,
        },
        status=200,
    )

    client = WhisperClient("http://example.test", timeout_sec=5)
    result = client.transcribe(wav_path, initial_prompt="prompt", hotwords=["Qwen"])

    assert result.success is True
    assert result.text == "hello world"
    assert result.segments == [
        TranscriptionSegment(start=0.0, end=1.0, text="hello"),
        TranscriptionSegment(start=1.0, end=2.0, text=" world"),
    ]
    request = responses.calls[0].request
    assert request.url == "http://example.test/transcribe"
    assert b'name="hotwords"' in request.body
    assert b"Qwen" in request.body
