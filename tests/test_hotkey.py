from voicetype.hotkey import RIGHT_ALT_NAME, RightAltToggleListener


def test_right_alt_listener_toggles_only_for_right_alt():
    calls = []
    listener = RightAltToggleListener(lambda: calls.append("toggle"))

    listener.handle_key_release(RIGHT_ALT_NAME)
    listener.handle_key_release("ctrl_r")
    listener.handle_key_release("ctrl_l")
    listener.handle_key_release("a")

    assert calls == ["toggle"]


def test_right_alt_listener_stop_stops_active_listener():
    calls = []

    class FakeListener:
        def stop(self):
            calls.append("stop")

    listener = RightAltToggleListener(lambda: None)
    listener._listener = FakeListener()

    listener.stop()

    assert calls == ["stop"]
