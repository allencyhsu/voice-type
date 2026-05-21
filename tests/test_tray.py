import voicetype.tray as tray
from voicetype.listener_runtime import ListenerStatus
from voicetype.tray import TrayController


class FakeRuntime:
    def __init__(self):
        self.status = ListenerStatus.READY
        self.started = False
        self.stopped = False

    def start_in_thread(self):
        self.started = True
        self.status = ListenerStatus.RUNNING

    def stop(self):
        self.stopped = True
        self.status = ListenerStatus.STOPPED


def test_tray_controller_starts_runtime():
    runtime = FakeRuntime()
    controller = TrayController(runtime=runtime)

    controller.start()

    assert runtime.started is True


def test_tray_status_label_uses_runtime_status():
    runtime = FakeRuntime()
    runtime.status = ListenerStatus.RUNNING
    controller = TrayController(runtime=runtime)

    assert controller.status_label() == "Status: Running"


def test_tray_controller_can_show_latest_log():
    messages = []

    controller = TrayController(
        runtime=FakeRuntime(),
        latest_log_provider=lambda: "latest log line",
        message_presenter=lambda title, message: messages.append((title, message)),
    )

    controller.show_latest_log()

    assert messages == [("VoiceType Latest Log", "latest log line")]


def test_show_message_uses_native_windows_message_box(monkeypatch):
    calls = []

    monkeypatch.setattr(tray.os, "name", "nt")
    monkeypatch.setattr(tray, "show_windows_message", lambda title, message: calls.append((title, message)))

    tray.show_message("VoiceType Latest Log", "latest log line")

    assert calls == [("VoiceType Latest Log", "latest log line")]


def test_tray_controller_stop_stops_runtime_and_icon():
    runtime = FakeRuntime()
    calls = []
    controller = TrayController(runtime=runtime)

    controller.quit(icon=type("FakeIcon", (), {"stop": lambda self: calls.append("icon-stop")})())

    assert runtime.stopped is True
    assert calls == ["icon-stop"]
