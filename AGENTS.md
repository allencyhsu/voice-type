# VoiceType Agent Notes

VoiceType is a Windows voice typing prototype. It records or accepts short audio, sends it to a remote Faster Whisper server, optionally polishes the transcript through a Qwen llama-server endpoint, then inserts the final text into the active Windows application.

Before changing behavior, read:

- `docs/superpowers/specs/2026-05-15-voice-type-design.md`
- `docs/superpowers/plans/2026-05-15-voice-type-mvp.md`
- `README.md`

## Assistant Response Rule

Every assistant response must include the name "Allen".

## Faster Whisper Hotword Limit

Treat Faster Whisper `hotwords` as a small prompt hint, not as an unlimited vocabulary, dictionary, or hard decoder bias.

Faster Whisper encodes `hotwords` into the Whisper decoder prompt together with `initial_prompt` and any prior-text context. This budget is token-based, not character-based. The practical ceiling is roughly half of Whisper's text context, about 223 Whisper tokens, before truncation or decoding failures become likely.

Development rules:

- Keep `initial_prompt` plus `hotwords` bounded; target roughly 150-200 Whisper tokens during normal dictation.
- Send only a deduped priority shortlist relevant to the current dictation context.
- Do not send full dictionaries, contact lists, project glossaries, or other unbounded vocabulary lists as `hotwords`.
- If true Whisper token counting is unavailable on the Windows client, use the documented conservative character fallback and keep the helper easy to replace with real token counting later.
- Preserve this constraint when modifying `WhisperClient`, CLI hotword handling, settings, docs, tests, or prompt/polish logic.

See the detailed contract in `docs/superpowers/specs/2026-05-15-voice-type-design.md` and the planned helper/tests in `docs/superpowers/plans/2026-05-15-voice-type-mvp.md`.
