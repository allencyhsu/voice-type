from typing import Annotated, Any, Literal

from pydantic import Field, TypeAdapter, ValidationError
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from voicetype.user_settings import load_user_settings


class UserJsonSettingsSource(PydanticBaseSettingsSource):
    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        loaded = load_user_settings(allowed_fields=self.settings_cls.model_fields).values
        validated: dict[str, Any] = {}
        for field_name, value in loaded.items():
            field = self.settings_cls.model_fields.get(field_name)
            if field is None:
                continue
            annotation = field.annotation
            if field.metadata:
                annotation = Annotated[annotation, *field.metadata]
            try:
                validated[field_name] = TypeAdapter(annotation).validate_python(value)
            except (TypeError, ValueError, ValidationError):
                continue
        return validated


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VOICETYPE_", env_file=".env")

    whisper_url: str = "http://forge2.tail9d0481.ts.net:8008"
    llm_base_url: str = "http://ai-srv.tail9d0481.ts.net:8001/v1"
    llm_model: str = "qwen3.6-35b"
    asr_timeout_sec: int = 120
    llm_timeout_sec: int = 20
    enable_llm: bool = True
    sample_rate: int = 16000
    channels: int = 1
    record_seconds: float = Field(default=8.0, gt=0)
    min_record_seconds: float = Field(default=0.7, gt=0)
    notify: Literal["overlay", "console", "toast", "off"] = "overlay"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            UserJsonSettingsSource(settings_cls),
            file_secret_settings,
        )
