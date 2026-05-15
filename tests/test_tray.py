from voicetype.listener_runtime import ListenerStatus
from voicetype.tray import TrayController


class FakeRuntime:
    def __init__(self):
        self.status = ListenerStatus.READY
        self.started = False

    def start_in_thread(self):
        self.started = True
        self.status = ListenerStatus.RUNNING


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
