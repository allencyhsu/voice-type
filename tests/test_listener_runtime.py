from voicetype.listener_runtime import ListenerStatus, VoiceTypeListenerRuntime


def test_runtime_starts_listener_in_background_thread():
    calls = []

    def fake_runner():
        calls.append("run")

    runtime = VoiceTypeListenerRuntime(listener_runner=fake_runner)

    runtime.start_in_thread()
    runtime.join(timeout=2)

    assert calls == ["run"]
    assert runtime.status == ListenerStatus.STOPPED


def test_runtime_marks_error_when_runner_raises():
    def fake_runner():
        raise RuntimeError("boom")

    runtime = VoiceTypeListenerRuntime(listener_runner=fake_runner)

    runtime.start_in_thread()
    runtime.join(timeout=2)

    assert runtime.status == ListenerStatus.ERROR
    assert runtime.error == "boom"
