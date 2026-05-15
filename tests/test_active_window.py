from voicetype.active_window import ActiveWindowContext, get_active_app_name, get_active_window_context


class FakeWindowsApi:
    def __init__(
        self,
        *,
        hwnd=123,
        title="Untitled - Notepad",
        pid=456,
        image_path="C:/Windows/System32/notepad.exe",
    ):
        self.hwnd = hwnd
        self.title = title
        self.pid = pid
        self.image_path = image_path

    def foreground_window(self):
        return self.hwnd

    def window_text(self, hwnd):
        return self.title

    def window_process_id(self, hwnd):
        return self.pid

    def process_image_path(self, process_id):
        return self.image_path


def test_get_active_window_context_uses_process_stem_as_app_name():
    context = get_active_window_context(api=FakeWindowsApi())

    assert context == ActiveWindowContext(
        app_name="notepad",
        window_title="Untitled - Notepad",
        process_id=456,
        process_path="C:/Windows/System32/notepad.exe",
    )


def test_get_active_window_context_falls_back_to_window_title_when_process_path_missing():
    context = get_active_window_context(
        api=FakeWindowsApi(title="VoiceType Test Window", image_path=None)
    )

    assert context.app_name == "VoiceType Test Window"
    assert context.process_path is None


def test_get_active_window_context_returns_none_when_no_foreground_window():
    assert get_active_window_context(api=FakeWindowsApi(hwnd=0)) is None


def test_get_active_app_name_returns_unknown_when_context_missing():
    assert get_active_app_name(context_provider=lambda: None) == "unknown"


def test_get_active_app_name_returns_context_app_name():
    assert get_active_app_name(
        context_provider=lambda: ActiveWindowContext(
            app_name="notepad",
            window_title="Untitled - Notepad",
            process_id=456,
            process_path="C:/Windows/System32/notepad.exe",
        )
    ) == "notepad"
