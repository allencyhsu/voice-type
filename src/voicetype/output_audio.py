from __future__ import annotations

import sys
from typing import Callable, Protocol


class OutputMuteGuard(Protocol):
    def mute_for_recording(self) -> None:
        raise NotImplementedError

    def restore(self) -> None:
        raise NotImplementedError


class EndpointVolume(Protocol):
    def GetMute(self) -> int:
        raise NotImplementedError

    def SetMute(self, muted: int, event_context) -> None:
        raise NotImplementedError


class NullOutputMuteGuard:
    def mute_for_recording(self) -> None:
        return None

    def restore(self) -> None:
        return None


class WindowsOutputMuteGuard:
    def __init__(
        self,
        endpoint_factory: Callable[[], EndpointVolume] | None = None,
    ) -> None:
        self._endpoint_factory = endpoint_factory or _default_endpoint_volume
        self._endpoint: EndpointVolume | None = None
        self._previous_muted: int | None = None
        self._is_muted = False

    def mute_for_recording(self) -> None:
        if self._is_muted:
            return

        endpoint = self._endpoint_factory()
        self._previous_muted = int(endpoint.GetMute())
        endpoint.SetMute(1, None)
        self._endpoint = endpoint
        self._is_muted = True

    def restore(self) -> None:
        if not self._is_muted or self._endpoint is None or self._previous_muted is None:
            return

        self._endpoint.SetMute(self._previous_muted, None)
        self._endpoint = None
        self._previous_muted = None
        self._is_muted = False


def create_output_mute_guard() -> OutputMuteGuard:
    if sys.platform != "win32":
        return NullOutputMuteGuard()
    return WindowsOutputMuteGuard()


def try_mute_for_recording(
    guard: OutputMuteGuard,
    *,
    report: Callable[[str], object] = print,
) -> None:
    try:
        guard.mute_for_recording()
    except Exception as exc:
        report(f"[VoiceType] Could not mute output audio: {exc}")


def try_restore_output(
    guard: OutputMuteGuard,
    *,
    report: Callable[[str], object] = print,
) -> None:
    try:
        guard.restore()
    except Exception as exc:
        report(f"[VoiceType] Could not restore output audio: {exc}")


def _default_endpoint_volume() -> EndpointVolume:
    from ctypes import POINTER, cast

    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))
