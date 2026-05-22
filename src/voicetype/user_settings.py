from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Iterable


USER_SETTING_FIELDS = {
    "whisper_url",
    "llm_base_url",
    "llm_model",
    "asr_timeout_sec",
    "llm_timeout_sec",
    "enable_llm",
    "sample_rate",
    "channels",
    "record_seconds",
    "min_record_seconds",
    "notify",
}


@dataclass(frozen=True)
class UserSettingsLoadResult:
    values: dict[str, Any]
    error: str | None = None


def default_user_settings_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    base_dir = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base_dir / "VoiceType" / "settings.json"


def load_user_settings(
    *,
    path: str | Path | None = None,
    allowed_fields: Iterable[str] | None = None,
) -> UserSettingsLoadResult:
    settings_path = Path(path) if path is not None else default_user_settings_path()
    allowed = set(allowed_fields or USER_SETTING_FIELDS)
    if not settings_path.exists():
        return UserSettingsLoadResult(values={})

    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("settings JSON must be an object")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return UserSettingsLoadResult(
            values={},
            error=f"Loaded defaults; settings file could not be read. {exc}",
        )

    return UserSettingsLoadResult(
        values={
            str(key): value
            for key, value in payload.items()
            if str(key) in allowed
        }
    )


def save_user_settings(
    values: dict[str, Any],
    *,
    path: str | Path | None = None,
    allowed_fields: Iterable[str] | None = None,
) -> Path:
    settings_path = Path(path) if path is not None else default_user_settings_path()
    allowed = set(allowed_fields or USER_SETTING_FIELDS)
    filtered = {
        str(key): value
        for key, value in values.items()
        if str(key) in allowed
    }
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(filtered, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return settings_path
