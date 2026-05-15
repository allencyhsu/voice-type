import os

from PIL import Image, ImageDraw

from voicetype.listener_runtime import VoiceTypeListenerRuntime, build_default_listener_runner
from voicetype.session_log import default_log_dir
from voicetype.startup import disable_startup, enable_startup, is_startup_enabled


class TrayController:
    def __init__(self, *, runtime: VoiceTypeListenerRuntime) -> None:
        self.runtime = runtime

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


def create_icon_image() -> Image.Image:
    image = Image.new("RGB", (64, 64), "#2563eb")
    draw = ImageDraw.Draw(image)
    draw.ellipse((14, 10, 50, 46), fill="#f97316")
    draw.rectangle((28, 42, 36, 54), fill="#fff7ed")
    draw.rectangle((20, 54, 44, 58), fill="#fff7ed")
    return image


def run_tray_app() -> None:
    import pystray

    runtime = VoiceTypeListenerRuntime(listener_runner=build_default_listener_runner())
    controller = TrayController(runtime=runtime)
    controller.start()

    icon = pystray.Icon(
        "VoiceType",
        create_icon_image(),
        "VoiceType",
        menu=pystray.Menu(
            pystray.MenuItem(lambda item: controller.status_label(), None, enabled=False),
            pystray.MenuItem("Open Logs", lambda icon, item: controller.open_logs()),
            pystray.MenuItem(lambda item: controller.startup_label(), lambda icon, item: controller.toggle_startup()),
            pystray.MenuItem("Quit VoiceType", lambda icon, item: icon.stop()),
        ),
    )
    icon.run()
