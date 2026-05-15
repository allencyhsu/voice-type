from dataclasses import dataclass
from pathlib import PureWindowsPath
import sys


@dataclass(frozen=True)
class ActiveWindowContext:
    app_name: str
    window_title: str
    process_id: int
    process_path: str | None


def get_active_app_name(*, context_provider=None) -> str:
    provider = context_provider or get_active_window_context
    context = provider()
    if context is None:
        return "unknown"
    return context.app_name or "unknown"


def get_active_window_context(*, api=None) -> ActiveWindowContext | None:
    try:
        active_api = api or WindowsApi()
    except RuntimeError:
        return None
    hwnd = active_api.foreground_window()
    if not hwnd:
        return None

    title = active_api.window_text(hwnd)
    process_id = active_api.window_process_id(hwnd)
    process_path = active_api.process_image_path(process_id)
    app_name = app_name_from_process_path(process_path) or title or "unknown"
    return ActiveWindowContext(
        app_name=app_name,
        window_title=title,
        process_id=process_id,
        process_path=process_path,
    )


def app_name_from_process_path(process_path: str | None) -> str | None:
    if not process_path:
        return None
    return PureWindowsPath(process_path).stem or None


class WindowsApi:
    def __init__(self) -> None:
        if sys.platform != "win32":
            raise RuntimeError("Active window detection is only available on Windows")
        import ctypes

        self._ctypes = ctypes
        self._user32 = ctypes.windll.user32
        self._kernel32 = ctypes.windll.kernel32

    def foreground_window(self) -> int:
        return int(self._user32.GetForegroundWindow())

    def window_text(self, hwnd: int) -> str:
        length = self._user32.GetWindowTextLengthW(hwnd)
        buffer = self._ctypes.create_unicode_buffer(length + 1)
        self._user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value

    def window_process_id(self, hwnd: int) -> int:
        process_id = self._ctypes.c_ulong()
        self._user32.GetWindowThreadProcessId(hwnd, self._ctypes.byref(process_id))
        return int(process_id.value)

    def process_image_path(self, process_id: int) -> str | None:
        process_query_limited_information = 0x1000
        handle = self._kernel32.OpenProcess(process_query_limited_information, False, process_id)
        if not handle:
            return None

        try:
            size = self._ctypes.c_ulong(32768)
            buffer = self._ctypes.create_unicode_buffer(size.value)
            if not self._kernel32.QueryFullProcessImageNameW(handle, 0, buffer, self._ctypes.byref(size)):
                return None
            return buffer.value
        finally:
            self._kernel32.CloseHandle(handle)
