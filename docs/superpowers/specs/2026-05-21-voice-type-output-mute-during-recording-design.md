# VoiceType Output Mute During Recording Design

## Summary

When VoiceType starts recording from the right Ctrl listener, it should temporarily mute the Windows default audio output device. When recording stops, VoiceType should restore the output mute state that existed before the recording began. This reduces feedback and background audio bleed into the microphone without changing the stable right Ctrl hotkey, microphone idle behavior, Whisper request flow, Qwen polish flow, or paste behavior.

## Goals

- Mute the Windows default output device only while an active recording is in progress.
- Restore the previous output mute state after recording stops.
- Preserve the user's original mute state if output was already muted before dictation.
- Keep the microphone closed while VoiceType is idle.
- Keep tray mode and CLI listener mode on the same listener core.
- Make the mute behavior testable without touching real Windows audio devices.

## Non-Goals

- No custom audio driver or virtual audio cable.
- No per-application audio session mixer in this change.
- No automatic microphone gain or input device switching.
- No change to the right Ctrl hotkey.
- No change to Faster Whisper hotword limits or Qwen correction memory behavior.

## User Flow

1. User places the caret in a text field.
2. User presses right Ctrl to start listening.
3. VoiceType opens the microphone and mutes the default Windows output device.
4. User speaks while other playback is muted.
5. User presses right Ctrl again to stop listening.
6. VoiceType stops recording and restores the previous Windows output mute state.
7. VoiceType normalizes audio, transcribes, optionally polishes, and pastes as it does today.

## Architecture

Add a small audio-output guard with a narrow interface:

```python
class OutputMuteGuard:
    def mute_for_recording(self) -> None: ...
    def restore(self) -> None: ...
```

The Windows implementation should use the default playback endpoint. In production, this can be backed by a library such as `pycaw`, because it exposes Windows Core Audio endpoint volume controls from Python. Tests should inject a fake guard rather than changing the real system volume.

The listener owns the guard lifecycle because it already owns the recording lifecycle:

- On the first right Ctrl press, after `ToggleRecorder.start()` succeeds, call `mute_for_recording()`.
- On the second right Ctrl press, after `ToggleRecorder.stop_to_wav()` returns, call `restore()` before audio normalization, ASR, Qwen, or paste work.
- In shutdown cleanup, if VoiceType exits while recording, cancel the recorder and restore output.

The fixed-duration `record` CLI command should use the same guard around `record_wav()` so active recording entry points behave consistently. Non-recording commands such as `transcribe`, `doctor`, `logs`, `memory`, and `tray` startup should not mute output by themselves.

## State Restoration

The guard should snapshot the pre-recording mute state before muting output. Restoration should set the endpoint mute value back to that snapshot:

- If output was unmuted before recording, unmute it after recording.
- If output was already muted before recording, leave it muted after recording.
- If muting fails, continue recording and log or print a diagnostic message.
- If restoration fails, do not block transcription or paste, but surface a diagnostic message.

The guard should be idempotent. Repeated `mute_for_recording()` calls during one recording should not overwrite the original snapshot, and repeated `restore()` calls should be harmless.

## Error Handling

- Recorder start failure: do not mute output.
- Mute failure: continue recording.
- Stop or short-recording path: restore output before returning to Ready.
- Transcription, Qwen, or paste failure: output should already have been restored before those steps.
- Keyboard interrupt while recording: cancel the recorder and restore output.

## Testing

- Unit test that listener start calls recorder start, then guard mute.
- Unit test that listener stop calls recorder stop, then guard restore before processing.
- Unit test that short recordings still restore output.
- Unit test that shutdown cleanup restores output if recording was active.
- Unit test the guard snapshot semantics with a fake endpoint object: unmuted restores to unmuted, already muted restores to muted, repeated calls are safe.
- Keep tests away from real Windows audio devices.

## Acceptance Criteria

- Right Ctrl starts recording and mutes Windows default output.
- Right Ctrl stops recording and restores the previous output mute state.
- Tray mode receives the same behavior because it reuses the listener core.
- `python -m pytest` passes.
- Documentation describes that output audio is muted only during active recording.
