from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VOICETYPE_", env_file=".env")

    whisper_url: str = "http://forge2.tail9d0481.ts.net:8008"
    llm_base_url: str = "http://forge2.tail9d0481.ts.net:8001/v1"
    llm_model: str = "qwen3.6-35b"
    asr_timeout_sec: int = 120
    llm_timeout_sec: int = 20
    enable_llm: bool = True
    sample_rate: int = 16000
    channels: int = 1
    record_seconds: float = Field(default=8.0, gt=0)
