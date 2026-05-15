import os
from collections.abc import Callable
from datetime import date

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
    ) -> None:
        self.runtime = runtime
        self.latest_log_provider = latest_log_provider or latest_log_text
        self.message_presenter = message_presenter or show_message

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

    def quit(self, icon) -> None:
        self.runtime.stop()
        icon.stop()


def latest_log_text() -> str:
    from voicetype.cli import format_log_record

    record = latest_session_record(day=date.today())
    if record is None:
        return "[VoiceType] No session log found for today."
    return format_log_record(record)


def show_message(title: str, message: str) -> None:
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
            pystray.MenuItem("Show Latest Log", lambda icon, item: controller.show_latest_log()),
            pystray.MenuItem("Open Logs", lambda icon, item: controller.open_logs()),
            pystray.MenuItem(lambda item: controller.startup_label(), lambda icon, item: controller.toggle_startup()),
            pystray.MenuItem("Quit VoiceType", lambda icon, item: controller.quit(icon)),
        ),
    )
    icon.run()
