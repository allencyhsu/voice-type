import json

from voicetype.user_settings import (
    UserSettingsLoadResult,
    default_user_settings_path,
    load_user_settings,
    save_user_settings,
)


def test_default_user_settings_path_uses_local_app_data(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert default_user_settings_path() == tmp_path / "VoiceType" / "settings.json"


def test_user_settings_round_trip_filters_unknown_keys(tmp_path):
    path = tmp_path / "settings.json"

    saved_path = save_user_settings(
        {
            "enable_llm": False,
            "llm_model": "custom-qwen",
            "unknown": "ignored",
        },
        path=path,
        allowed_fields={"enable_llm", "llm_model"},
    )

    assert saved_path == path
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "enable_llm": False,
        "llm_model": "custom-qwen",
    }
    assert load_user_settings(path=path).values == {
        "enable_llm": False,
        "llm_model": "custom-qwen",
    }


def test_load_user_settings_missing_file_is_empty(tmp_path):
    result = load_user_settings(path=tmp_path / "missing.json")

    assert result == UserSettingsLoadResult(values={})


def test_load_user_settings_malformed_file_falls_back_to_empty(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{bad json}", encoding="utf-8")

    result = load_user_settings(path=path)

    assert result.values == {}
    assert result.error is not None
    assert "settings file could not be read" in result.error
