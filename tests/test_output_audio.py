from voicetype.output_audio import (
    NullOutputMuteGuard,
    WindowsOutputMuteGuard,
    try_mute_for_recording,
    try_restore_output,
)


class FakeEndpointVolume:
    def __init__(self, muted: bool = False) -> None:
        self.muted = muted
        self.calls: list[tuple[str, int | None]] = []

    def GetMute(self) -> int:
        self.calls.append(("GetMute", None))
        return 1 if self.muted else 0

    def SetMute(self, muted: int, event_context) -> None:
        self.calls.append(("SetMute", muted))
        self.muted = bool(muted)


class RaisingGuard:
    def mute_for_recording(self) -> None:
        raise RuntimeError("mute failed")

    def restore(self) -> None:
        raise RuntimeError("restore failed")


def test_windows_guard_restores_unmuted_output_state():
    endpoint = FakeEndpointVolume(muted=False)
    guard = WindowsOutputMuteGuard(endpoint_factory=lambda: endpoint)

    guard.mute_for_recording()
    assert endpoint.muted is True

    guard.restore()
    assert endpoint.muted is False
    assert endpoint.calls == [
        ("GetMute", None),
        ("SetMute", 1),
        ("SetMute", 0),
    ]


def test_windows_guard_preserves_preexisting_muted_state():
    endpoint = FakeEndpointVolume(muted=True)
    guard = WindowsOutputMuteGuard(endpoint_factory=lambda: endpoint)

    guard.mute_for_recording()
    guard.restore()

    assert endpoint.muted is True
    assert endpoint.calls == [
        ("GetMute", None),
        ("SetMute", 1),
        ("SetMute", 1),
    ]


def test_windows_guard_is_idempotent_during_one_recording():
    endpoint = FakeEndpointVolume(muted=False)
    guard = WindowsOutputMuteGuard(endpoint_factory=lambda: endpoint)

    guard.mute_for_recording()
    endpoint.muted = False
    guard.mute_for_recording()
    guard.restore()
    guard.restore()

    assert endpoint.muted is False
    assert endpoint.calls == [
        ("GetMute", None),
        ("SetMute", 1),
        ("SetMute", 0),
    ]


def test_null_guard_is_safe_to_call_repeatedly():
    guard = NullOutputMuteGuard()

    guard.mute_for_recording()
    guard.mute_for_recording()
    guard.restore()
    guard.restore()


def test_safe_helpers_report_mute_and_restore_failures():
    messages: list[str] = []
    guard = RaisingGuard()

    try_mute_for_recording(guard, report=messages.append)
    try_restore_output(guard, report=messages.append)

    assert messages == [
        "[VoiceType] Could not mute output audio: mute failed",
        "[VoiceType] Could not restore output audio: restore failed",
    ]
