from collections.abc import Callable


class ConsoleNotifier:
    def notify(self, message: str) -> None:
        print(f"[VoiceType] {message}")


class NullNotifier:
    def notify(self, message: str) -> None:
        return


class ToastNotifier:
    def __init__(self, *, toast_factory: Callable | None = None) -> None:
        self.toast_factory = toast_factory

    def notify(self, message: str) -> None:
        toast_factory = self.toast_factory or _load_toast_factory()
        toast = toast_factory(
            app_id="VoiceType",
            title="VoiceType",
            msg=message,
            duration="short",
        )
        toast.show()


def create_notifier(mode: str):
    if mode == "console":
        return ConsoleNotifier()
    if mode == "toast":
        return ToastNotifier()
    if mode == "off":
        return NullNotifier()
    raise ValueError(f"Unsupported notifier mode: {mode}")


def _load_toast_factory():
    from winotify import Notification

    return Notification
