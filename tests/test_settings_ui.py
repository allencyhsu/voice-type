from dataclasses import dataclass

from voicetype.memory import CorrectionEntry, CorrectionType
from voicetype.settings_ui import SettingsUiModel
from voicetype.user_settings import load_user_settings


@dataclass
class FakeMemoryStore:
    entries: list[CorrectionEntry]
    removed: list[str]

    def load(self):
        return list(self.entries)

    def add(self, entry_type, *, wrong, correct):
        entry = CorrectionEntry(
            id="entry-new",
            type=CorrectionType(str(entry_type)),
            wrong=wrong,
            correct=correct,
            scope="global",
            created_at="2026-05-23T10:00:00+08:00",
            updated_at="2026-05-23T10:00:00+08:00",
            uses=0,
        )
        self.entries.append(entry)
        return entry

    def remove(self, entry_id):
        self.removed.append(entry_id)
        before = len(self.entries)
        self.entries = [entry for entry in self.entries if entry.id != entry_id]
        return len(self.entries) != before


def test_settings_ui_model_saves_user_settings(tmp_path):
    path = tmp_path / "settings.json"
    model = SettingsUiModel(settings_path=path)

    status = model.save_settings(
        {
            "whisper_url": " http://whisper.test ",
            "llm_base_url": "http://qwen.test/v1",
            "llm_model": "qwen-custom",
            "enable_llm": False,
            "notify": "toast",
            "record_seconds": "6.5",
            "min_record_seconds": "0.9",
        }
    )

    assert status == "Saved. Restart VoiceType for all settings to take effect."
    assert load_user_settings(path=path).values == {
        "whisper_url": "http://whisper.test",
        "llm_base_url": "http://qwen.test/v1",
        "llm_model": "qwen-custom",
        "enable_llm": False,
        "notify": "toast",
        "record_seconds": 6.5,
        "min_record_seconds": 0.9,
    }


def test_settings_ui_model_rejects_invalid_notify_mode(tmp_path):
    model = SettingsUiModel(settings_path=tmp_path / "settings.json")

    status = model.save_settings({"notify": "loud"})

    assert "Unsupported notification mode" in status


def test_settings_ui_model_rejects_blank_service_values(tmp_path):
    model = SettingsUiModel(settings_path=tmp_path / "settings.json")

    status = model.save_settings({"whisper_url": "  "})

    assert "whisper_url cannot be empty" in status


def test_settings_ui_model_preserves_advanced_user_settings(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"asr_timeout_sec": 90}\n', encoding="utf-8")
    model = SettingsUiModel(settings_path=path)

    model.save_settings({"notify": "off"})

    assert load_user_settings(path=path).values == {
        "asr_timeout_sec": 90,
        "notify": "off",
    }


def test_settings_ui_model_toggles_startup_immediately(tmp_path):
    calls = []
    model = SettingsUiModel(
        settings_path=tmp_path / "settings.json",
        startup_enabled=lambda: False,
        enable_startup=lambda: calls.append("enable"),
        disable_startup=lambda: calls.append("disable"),
    )

    assert model.set_startup_enabled(True) == "Start at login enabled."
    assert model.set_startup_enabled(False) == "Start at login disabled."
    assert calls == ["enable", "disable"]


def test_settings_ui_model_log_actions_call_callbacks(tmp_path):
    calls = []
    model = SettingsUiModel(
        settings_path=tmp_path / "settings.json",
        open_logs=lambda: calls.append("open-logs"),
        show_latest_log=lambda: calls.append("show-latest-log"),
    )

    assert model.open_logs() == "Opened logs."
    assert model.show_latest_log() == "Opened latest log."
    assert calls == ["open-logs", "show-latest-log"]


def test_settings_ui_model_reports_log_action_errors(tmp_path):
    def raise_error():
        raise OSError("cannot open")

    model = SettingsUiModel(
        settings_path=tmp_path / "settings.json",
        open_logs=raise_error,
        show_latest_log=raise_error,
    )

    assert model.open_logs() == "Could not open logs: cannot open"
    assert model.show_latest_log() == "Could not open latest log: cannot open"


def test_settings_ui_model_manages_correction_memory(tmp_path):
    store = FakeMemoryStore(entries=[], removed=[])
    model = SettingsUiModel(settings_path=tmp_path / "settings.json", memory_store=store)

    entry = model.add_correction("term", wrong="cue and", correct="Qwen")
    entries = model.load_corrections()
    removed_status = model.remove_correction(entry.id)

    assert entry.id == "entry-new"
    assert entries == [entry]
    assert removed_status == "Removed correction memory entry."
    assert store.removed == ["entry-new"]
