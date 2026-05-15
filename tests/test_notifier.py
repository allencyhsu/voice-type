from voicetype.notifier import ConsoleNotifier, NullNotifier, ToastNotifier, create_notifier


def test_console_notifier_prints_prefixed_status(capsys):
    notifier = ConsoleNotifier()

    notifier.notify("Listening")

    assert capsys.readouterr().out == "[VoiceType] Listening\n"


def test_null_notifier_ignores_messages(capsys):
    NullNotifier().notify("Listening")

    assert capsys.readouterr().out == ""


def test_create_notifier_returns_requested_mode():
    assert isinstance(create_notifier("console"), ConsoleNotifier)
    assert isinstance(create_notifier("off"), NullNotifier)
    assert isinstance(create_notifier("toast"), ToastNotifier)


def test_toast_notifier_delegates_to_toast_factory():
    calls = []

    class FakeToast:
        def __init__(self, *, app_id, title, msg, duration):
            calls.append(("init", app_id, title, msg, duration))

        def show(self):
            calls.append(("show",))

    notifier = ToastNotifier(toast_factory=FakeToast)

    notifier.notify("Listening...")

    assert calls == [
        ("init", "VoiceType", "VoiceType", "Listening...", "short"),
        ("show",),
    ]
