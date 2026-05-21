from voicetype.settings import Settings


def test_default_settings_match_voice_type_services():
    settings = Settings()

    assert settings.whisper_url == "http://forge2.tail9d0481.ts.net:8008"
    assert settings.llm_base_url == "http://ai-srv.tail9d0481.ts.net:8001/v1"
    assert settings.llm_model == "qwen3.6-35b"
    assert settings.enable_llm is True
    assert settings.sample_rate == 16000
    assert settings.channels == 1
    assert settings.min_record_seconds == 0.7


def test_settings_read_environment_overrides(monkeypatch):
    monkeypatch.setenv("VOICETYPE_ENABLE_LLM", "false")
    monkeypatch.setenv("VOICETYPE_LLM_MODEL", "custom-model")

    settings = Settings()

    assert settings.enable_llm is False
    assert settings.llm_model == "custom-model"


from pathlib import Path


def _env_example_values() -> dict[str, str]:
    env_example = Path(__file__).resolve().parents[1] / ".env-example"
    values: dict[str, str] = {}
    for line in env_example.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, separator, value = stripped.partition("=")
        assert separator == "=", f"Invalid .env-example line: {line}"
        values[key] = value
    return values


def _settings_default_value(value: object) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def test_env_example_keys_match_settings_fields():
    env_values = _env_example_values()
    keys = set(env_values)
    expected_keys = {
        "VOICETYPE_WHISPER_URL",
        "VOICETYPE_LLM_BASE_URL",
        "VOICETYPE_LLM_MODEL",
        "VOICETYPE_ASR_TIMEOUT_SEC",
        "VOICETYPE_LLM_TIMEOUT_SEC",
        "VOICETYPE_ENABLE_LLM",
        "VOICETYPE_SAMPLE_RATE",
        "VOICETYPE_CHANNELS",
        "VOICETYPE_RECORD_SECONDS",
        "VOICETYPE_MIN_RECORD_SECONDS",
    }

    assert expected_keys <= keys

    prefix = "VOICETYPE_"
    settings_fields = set(Settings.model_fields)
    unknown_fields = {
        key.removeprefix(prefix).lower()
        for key in keys
        if key.startswith(prefix)
    } - settings_fields

    assert unknown_fields == set()

    settings = Settings()
    for key, env_value in env_values.items():
        if not key.startswith(prefix):
            continue
        field_name = key.removeprefix(prefix).lower()
        assert env_value == _settings_default_value(getattr(settings, field_name))
