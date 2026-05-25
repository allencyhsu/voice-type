from voicetype.notifier import (
    ConsoleNotifier,
    NullNotifier,
    OverlayNotifier,
    ToastNotifier,
    create_notifier,
    overlay_geometry,
    overlay_presentation_for,
)


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
    assert isinstance(create_notifier("overlay"), OverlayNotifier)


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


def test_overlay_notifier_delegates_to_overlay_factory():
    calls = []

    class FakeOverlay:
        def notify(self, message):
            calls.append(message)

    notifier = OverlayNotifier(overlay_factory=FakeOverlay)

    notifier.notify("Processing...")

    assert calls == ["Processing..."]


def test_overlay_notifier_suppresses_diagnostic_messages():
    calls = []

    class FakeOverlay:
        def notify(self, message):
            calls.append(message)

    notifier = OverlayNotifier(overlay_factory=FakeOverlay)

    notifier.notify("Captured 1.23s, 1234 bytes: C:\\Temp\\voicetype-test.ogg")
    notifier.notify("Normalized audio gain=50.0x peak=0.0100->0.5000")
    notifier.notify("Listening...")

    assert calls == ["Listening..."]


def test_overlay_listening_status_stays_visible_until_next_status():
    presentation = overlay_presentation_for("Listening...")

    assert presentation.hide_after_ms is None


def test_overlay_processing_status_auto_hides():
    presentation = overlay_presentation_for("Processing...")

    assert presentation.hide_after_ms == 1800


def test_overlay_uses_vivid_non_monochrome_colors_for_listening():
    presentation = overlay_presentation_for("Listening...")

    assert presentation.bg == "#dc2626"
    assert presentation.fg == "#fff7ed"
    assert presentation.bg not in {"#000000", "#111111", "#ffffff", "#f9fafb"}


def test_overlay_geometry_places_window_above_taskbar():
    x, y = overlay_geometry(width=320, height=56, screen_width=1920, screen_height=1080)

    assert x == 800
    assert y == 936
