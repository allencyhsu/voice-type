import os
from collections.abc import Callable
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw

from voicetype.listener_runtime import VoiceTypeListenerRuntime, build_default_listener_runner
from voicetype.session_log import default_log_dir, latest_session_record
from voicetype.startup import disable_startup, enable_startup, is_startup_enabled


class TrayController:
    def __init__(
        self,
        *,
        runtime: VoiceTypeListenerRuntime,
        latest_log_provider: Callable[[], str] | None = None,
        message_presenter: Callable[[str, str], None] | None = None,
        settings_opener: Callable[[], None] | None = None,
    ) -> None:
        self.runtime = runtime
        self.latest_log_provider = latest_log_provider or latest_log_text
        self.message_presenter = message_presenter or show_latest_log_file
        self.settings_opener = settings_opener or open_settings

    def start(self) -> None:
        self.runtime.start_in_thread()

    def status_label(self) -> str:
        return f"Status: {self.runtime.status}"

    def open_logs(self) -> None:
        log_dir = default_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(log_dir)

    def startup_label(self) -> str:
        return f"Start at Login: {'On' if is_startup_enabled() else 'Off'}"

    def toggle_startup(self) -> None:
        if is_startup_enabled():
            disable_startup()
        else:
            enable_startup()

    def show_latest_log(self) -> None:
        self.message_presenter("VoiceType Latest Log", self.latest_log_provider())

    def open_settings(self) -> None:
        self.settings_opener()

    def quit(self, icon) -> None:
        self.runtime.stop()
        icon.stop()


def latest_log_text() -> str:
    from voicetype.cli import format_log_record

    record = latest_session_record(day=date.today())
    if record is None:
        return "[VoiceType] No session log found for today."
    return format_log_record(record)


def show_latest_log_file(
    title: str,
    message: str,
    *,
    base_dir: str | Path | None = None,
    opener: Callable[[Path], object] | None = None,
) -> Path:
    output_dir = Path(base_dir) if base_dir is not None else default_log_dir().parent
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "latest-log.txt"
    output_path.write_text(f"{title}\n\n{message}\n", encoding="utf-8")
    open_file = opener or os.startfile
    open_file(output_path)
    return output_path


def open_settings() -> None:
    from voicetype.settings_ui import open_settings_window

    open_settings_window()


def show_message(title: str, message: str) -> None:
    if os.name == "nt":
        show_windows_message(title, message)
        return

    show_tk_message(title, message)


def show_windows_message(title: str, message: str) -> None:
    import ctypes

    mb_ok = 0x00000000
    mb_icon_information = 0x00000040
    mb_topmost = 0x00040000
    ctypes.windll.user32.MessageBoxW(None, message, title, mb_ok | mb_icon_information | mb_topmost)


def show_tk_message(title: str, message: str) -> None:
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        messagebox.showinfo(title, message, parent=root)
    finally:
        root.destroy()


def create_icon_image() -> Image.Image:
    image = Image.new("RGB", (64, 64), "#2563eb")
    draw = ImageDraw.Draw(image)
    draw.ellipse((14, 10, 50, 46), fill="#f97316")
    draw.rectangle((28, 42, 36, 54), fill="#fff7ed")
    draw.rectangle((20, 54, 44, 58), fill="#fff7ed")
    return image


def run_tray_app() -> None:
    import pystray

    stop_listener_holder: dict[str, Callable[[], None]] = {}
    runtime = VoiceTypeListenerRuntime(
        listener_runner=lambda: None,
        stop_listener=lambda: stop_listener_holder.get("stop", lambda: None)(),
    )
    runtime.listener_runner = build_default_listener_runner(
        status_callback=runtime.set_status,
        stop_listener_holder=stop_listener_holder,
    )
    controller = TrayController(runtime=runtime)
    controller.start()

    icon = pystray.Icon(
        "VoiceType",
        create_icon_image(),
        "VoiceType",
        menu=pystray.Menu(
            pystray.MenuItem(lambda item: controller.status_label(), None, enabled=False),
            pystray.MenuItem("Settings...", lambda icon, item: controller.open_settings()),
            pystray.MenuItem("Show Latest Log", lambda icon, item: controller.show_latest_log()),
            pystray.MenuItem("Open Logs", lambda icon, item: controller.open_logs()),
            pystray.MenuItem(lambda item: controller.startup_label(), lambda icon, item: controller.toggle_startup()),
            pystray.MenuItem("Quit VoiceType", lambda icon, item: controller.quit(icon)),
        ),
    )
    icon.run()
