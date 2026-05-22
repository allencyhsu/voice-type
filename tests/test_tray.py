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


def test_tray_controller_opens_settings_window():
    calls = []
    controller = TrayController(runtime=FakeRuntime(), settings_opener=lambda: calls.append("settings"))

    controller.open_settings()

    assert calls == ["settings"]


def test_default_show_latest_log_writes_file_and_opens_it(tmp_path):
    opened = []

    path = tray.show_latest_log_file(
        "VoiceType Latest Log",
        "latest log line",
        base_dir=tmp_path,
        opener=lambda path: opened.append(path),
    )

    assert path == tmp_path / "latest-log.txt"
    assert path.read_text(encoding="utf-8") == "VoiceType Latest Log\n\nlatest log line\n"
    assert opened == [path]


def test_tray_controller_defaults_to_latest_log_file_presenter(monkeypatch):
    calls = []

    monkeypatch.setattr(tray, "show_latest_log_file", lambda title, message: calls.append((title, message)))
    controller = TrayController(
        runtime=FakeRuntime(),
        latest_log_provider=lambda: "latest log line",
    )

    controller.show_latest_log()

    assert calls == [("VoiceType Latest Log", "latest log line")]


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
