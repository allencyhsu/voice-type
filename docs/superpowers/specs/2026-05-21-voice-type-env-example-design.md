# VoiceType Env Example Design

## Summary

VoiceType already reads settings from environment variables and a local `.env` file through `pydantic-settings`. Add a tracked `.env-example` template so settings can be adjusted later without editing code or committing local machine-specific values.

## Goals

- Provide a copyable `.env-example` with the common `VOICETYPE_*` settings.
- Keep real local settings in `.env`, which remains ignored by git.
- Document the `.env-example` to `.env` workflow in user-facing docs.
- Add a lightweight regression test so `.env-example` keys stay aligned with `Settings`.

## Non-Goals

- No new settings UI in this change.
- No change to default endpoint values.
- No change to environment-variable priority.
- No secrets or personal local paths in `.env-example`.
- No change to Faster Whisper hotword limits, Qwen correction memory, tray behavior, or output-mute behavior.

## Settings Template

The `.env-example` file should include:

- `VOICETYPE_WHISPER_URL`
- `VOICETYPE_LLM_BASE_URL`
- `VOICETYPE_LLM_MODEL`
- `VOICETYPE_ASR_TIMEOUT_SEC`
- `VOICETYPE_LLM_TIMEOUT_SEC`
- `VOICETYPE_ENABLE_LLM`
- `VOICETYPE_SAMPLE_RATE`
- `VOICETYPE_CHANNELS`
- `VOICETYPE_RECORD_SECONDS`
- `VOICETYPE_MIN_RECORD_SECONDS`

Values should match current `Settings` defaults. Comments should be concise and should explain that `.env` is local and ignored.

## Testing

Add a test that parses `.env-example`, extracts non-comment keys, removes the `VOICETYPE_` prefix, maps them to lowercase settings field names, and confirms each key exists on `Settings`. The test should also assert that the template includes the main service endpoint keys.

## Documentation

Update `README.md` setup instructions to show:

```powershell
Copy-Item .env-example .env
```

Then explain that `.env` can be edited for endpoints, timeouts, recording defaults, and LLM enablement, while direct environment variables still override `.env` values.

Update `CODEX_HANDOFF.md` so future agents know `.env-example` is the tracked template and `.env` is the ignored local override file.
