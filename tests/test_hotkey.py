from voicetype.hotkey import RIGHT_CTRL_NAME, RightCtrlToggleListener


def test_right_ctrl_listener_toggles_only_for_right_ctrl():
    calls = []
    listener = RightCtrlToggleListener(lambda: calls.append("toggle"))

    listener.handle_key_release(RIGHT_CTRL_NAME)
    listener.handle_key_release("alt_r")
    listener.handle_key_release("ctrl_l")
    listener.handle_key_release("a")

    assert calls == ["toggle"]


def test_right_ctrl_listener_stop_stops_active_listener():
    calls = []

    class FakeListener:
        def stop(self):
            calls.append("stop")

    listener = RightCtrlToggleListener(lambda: None)
    listener._listener = FakeListener()

    listener.stop()

    assert calls == ["stop"]
