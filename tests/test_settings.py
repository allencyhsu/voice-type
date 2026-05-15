from voicetype.settings import Settings


def test_default_settings_match_voice_type_services():
    settings = Settings()

    assert settings.whisper_url == "http://forge2.tail9d0481.ts.net:8008"
    assert settings.llm_base_url == "http://ai-srv.tail9d0481.ts.net:8001/v1"
    assert settings.llm_model == "qwen3.6-35b"
    assert settings.enable_llm is True
    assert settings.sample_rate == 16000
    assert settings.channels == 1


def test_settings_read_environment_overrides(monkeypatch):
    monkeypatch.setenv("VOICETYPE_ENABLE_LLM", "false")
    monkeypatch.setenv("VOICETYPE_LLM_MODEL", "custom-model")

    settings = Settings()

    assert settings.enable_llm is False
    assert settings.llm_model == "custom-model"
