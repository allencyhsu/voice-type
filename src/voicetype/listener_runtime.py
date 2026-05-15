from argparse import Namespace
from collections.abc import Callable
from enum import StrEnum
import threading


class ListenerStatus(StrEnum):
    READY = "Ready"
    RUNNING = "Running"
    STOPPED = "Stopped"
    ERROR = "Error"


class VoiceTypeListenerRuntime:
    def __init__(self, *, listener_runner: Callable[[], None]) -> None:
        self.listener_runner = listener_runner
        self.status = ListenerStatus.READY
        self.error: str | None = None
        self._thread: threading.Thread | None = None

    def start_in_thread(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="voicetype-listener", daemon=True)
        self._thread.start()

    def join(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        self.status = ListenerStatus.RUNNING
        try:
            self.listener_runner()
            self.status = ListenerStatus.STOPPED
        except Exception as exc:
            self.error = str(exc)
            self.status = ListenerStatus.ERROR


def build_default_listener_runner() -> Callable[[], None]:
    from voicetype.cli import run_listen
    from voicetype.injector import TextInjector
    from voicetype.pipeline import DictationPipeline
    from voicetype.qwen_client import QwenClient
    from voicetype.settings import Settings
    from voicetype.whisper_client import WhisperClient

    settings = Settings()
    whisper = WhisperClient(settings.whisper_url, timeout_sec=settings.asr_timeout_sec)
    qwen = QwenClient(settings.llm_base_url, settings.llm_model, settings.llm_timeout_sec) if settings.enable_llm else None
    pipeline = DictationPipeline(
        whisper,
        qwen,
        TextInjector(),
        enable_llm=settings.enable_llm,
    )
    args = Namespace(
        no_paste=False,
        no_llm=not settings.enable_llm,
        hotword=[],
        min_seconds=None,
        notify="overlay",
    )
    return lambda: run_listen(args, settings, pipeline)
