from types import SimpleNamespace
import sys
from pathlib import Path

import voicetype.tray as tray
from voicetype.listener_runtime import ListenerStatus
from voicetype.tray import TrayController


class FakeRuntime:
    def __init__(self, events=None):
        self.status = ListenerStatus.READY
        self.started = False
        self.stopped = False
        self.events = events

    def start_in_thread(self):
        if self.events is not None:
            self.events.append("runtime-start")
        self.started = True
        self.status = ListenerStatus.RUNNING

    def stop(self):
        if self.events is not None:
            self.events.append("runtime-stop")
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


def test_build_restart_command_prefers_pythonw_for_tray_mode(tmp_path):
    scripts = tmp_path / "Scripts"
    scripts.mkdir()
    python = scripts / "python.exe"
    pythonw = scripts / "pythonw.exe"
    python.write_text("", encoding="utf-8")
    pythonw.write_text("", encoding="utf-8")

    assert tray.build_restart_command(python_executable=python) == [
        str(pythonw),
        "-m",
        "voicetype",
        "tray",
    ]


def test_start_replacement_process_launches_restart_command(tmp_path, monkeypatch):
    calls = []

    monkeypatch.chdir(tmp_path)
    tray.start_replacement_process(
        python_executable="C:/Python/python.exe",
        popen=lambda args, **kwargs: calls.append((args, kwargs)) or object(),
    )

    assert calls == [
        (
            [str(Path("C:/Python/python.exe")), "-m", "voicetype", "tray"],
            {"cwd": str(tmp_path)},
        )
    ]


def test_tray_controller_restart_starts_replacement_then_stops_runtime_and_icon():
    events = []
    runtime = FakeRuntime(events)
    controller = TrayController(runtime=runtime, restart_starter=lambda: events.append("start-new-process"))
    icon = type("FakeIcon", (), {"stop": lambda self: events.append("icon-stop")})()

    controller.restart(icon)

    assert runtime.stopped is True
    assert events == ["start-new-process", "runtime-stop", "icon-stop"]


def test_tray_controller_restart_failure_keeps_current_tray_running():
    messages = []
    icon_events = []
    runtime = FakeRuntime()

    def fail_restart():
        raise OSError("cannot launch")

    controller = TrayController(
        runtime=runtime,
        restart_starter=fail_restart,
        message_presenter=lambda title, message: messages.append((title, message)),
    )
    icon = type("FakeIcon", (), {"stop": lambda self: icon_events.append("icon-stop")})()

    controller.restart(icon)

    assert runtime.stopped is False
    assert icon_events == []
    assert messages == [("VoiceType Restart Failed", "Could not restart VoiceType: cannot launch")]


def test_run_tray_app_menu_includes_restart_action(monkeypatch):
    menu_items = []

    class FakeMenuItem:
        def __init__(self, text, action, enabled=True):
            self.text = text
            self.action = action
            self.enabled = enabled
            menu_items.append(self)

    class FakeMenu:
        def __init__(self, *items):
            self.items = items

    class FakeIcon:
        def __init__(self, name, image, title, menu):
            self.name = name
            self.image = image
            self.title = title
            self.menu = menu

        def run(self):
            return None

    fake_pystray = SimpleNamespace(Icon=FakeIcon, Menu=FakeMenu, MenuItem=FakeMenuItem)
    monkeypatch.setitem(sys.modules, "pystray", fake_pystray)
    monkeypatch.setattr(tray, "build_default_listener_runner", lambda **kwargs: lambda: None)
    monkeypatch.setattr(tray.TrayController, "start", lambda self: None)

    tray.run_tray_app()

    assert "Restart VoiceType" in [item.text for item in menu_items if isinstance(item.text, str)]
