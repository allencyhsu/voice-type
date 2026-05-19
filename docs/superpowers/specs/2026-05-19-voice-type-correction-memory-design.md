# VoiceType Correction Memory v1 Design

## Summary

VoiceType Correction Memory v1 adds a local, user-controlled memory layer for ASR correction. The first version supports:

- A: confirmed terms, names, product names, and technical vocabulary.
- B: common ASR phrase mistakes and their corrections.

The memory is used primarily by Qwen during the polish step. Faster Whisper hotwords remain a very small hint list and must not become a dictionary, glossary, contact list, or long-term correction memory.

## Goals

- Store user-approved term and phrase corrections locally.
- Retrieve a small relevant correction set for each raw ASR transcript.
- Send relevant corrections to Qwen so it can repair ASR output after transcription.
- Keep the ASR-only path usable when Qwen is unavailable.
- Keep Faster Whisper hotwords strictly capped and intentionally sparse.
- Log which correction memory entries were selected for a dictation session.

## Non-Goals

- Do not train or fine-tune Faster Whisper.
- Do not send full correction memory to Faster Whisper.
- Do not build a cloud sync or account system.
- Do not automatically rewrite arbitrary text outside the dictation pipeline.
- Do not add broad style memory in v1. Style memory can be a later v2 feature.

## Faster Whisper Hotword Policy

Faster Whisper `hotwords` are prompt hints, not a correction database. VoiceType must apply all of these limits before sending the transcription request:

- Send at most 5 hotwords to Faster Whisper.
- Each hotword must be at most 5 Unicode characters after trimming and whitespace normalization.
- Empty values are ignored.
- Duplicate values are removed while preserving first-seen priority order.
- Phrase corrections are never sent to Faster Whisper.
- Long terms remain available to Qwen correction memory but are excluded from Faster Whisper.

The client should keep the existing token-budget understanding from the MVP spec: `initial_prompt` plus `hotwords` competes for Whisper decoder prompt space. The stricter 5-by-5 rule is the product-level default for VoiceType.

## Correction Memory Store

Store memory locally as JSONL:

```text
%LOCALAPPDATA%\VoiceType\memory\corrections.jsonl
```

Each line is one correction entry:

```json
{
  "id": "uuid",
  "type": "term",
  "wrong": "cue and",
  "correct": "Qwen",
  "scope": "global",
  "created_at": "2026-05-19T10:00:00+08:00",
  "updated_at": "2026-05-19T10:00:00+08:00",
  "uses": 0
}
```

Fields:

- `id`: stable UUID string.
- `type`: `term` or `phrase`.
- `wrong`: optional ASR mistake text. It may be empty for a pure vocabulary term.
- `correct`: required correction text.
- `scope`: v1 uses `global`. Later versions may add app-specific scope.
- `created_at` and `updated_at`: ISO timestamps.
- `uses`: count of times the entry was selected for a session.

The store must preserve Unicode text and write with UTF-8.

## Retrieval

For each raw ASR transcript:

1. Load active correction entries.
2. Normalize whitespace for matching.
3. Select entries whose `wrong` appears in the raw transcript.
4. Select short `term` entries whose `correct` appears to be relevant by simple case-insensitive containment or explicit CLI/user selection.
5. Limit the Qwen correction payload to a small bounded list, default 20 entries.

The selection should favor:

1. Exact `wrong` phrase matches.
2. Recently used or frequently used entries.
3. Short confirmed terms.
4. Stable first-seen order as a tie breaker.

## Qwen Payload

Qwen receives:

- raw ASR transcript
- focused app name when available
- user CLI hotwords
- selected correction memory entries
- Chinese script hint from the existing script detector

Example user payload:

```json
{
  "app": "Code",
  "mode": "dictation",
  "raw_transcript": "cue and should fix this",
  "hotwords": ["Qwen"],
  "correction_memory": [
    {
      "id": "entry-id",
      "type": "term",
      "wrong": "cue and",
      "correct": "Qwen"
    }
  ],
  "chinese_script": "traditional"
}
```

Prompt rules:

- Use correction memory only when it matches the transcript.
- Prefer exact correction memory over guessing.
- Do not invent new terms.
- Do not assume the Faster Whisper hotword list is exhaustive.
- Preserve Traditional Chinese when the transcript is Traditional Chinese.
- Return only JSON with `action` and `text`.

## CLI

Add a `memory` command group:

```powershell
python -m voicetype memory add --type term --wrong "cue and" --correct "Qwen"
python -m voicetype memory add --type phrase --wrong "bad phrase" --correct "correct phrase"
python -m voicetype memory list
python -m voicetype memory remove <id>
python -m voicetype memory learn --from-last --corrected "final corrected text"
```

`learn --from-last` reads the latest session log record and creates a conservative `phrase` entry from the latest raw ASR text to the supplied corrected text. It must not overwrite existing memory automatically.

## Logging

Session logs should include:

- selected correction memory entry IDs
- Qwen correction memory count
- Whisper hotword count before filtering
- Whisper hotword count after filtering
- final hotwords sent to Faster Whisper

Logs must continue to include raw and final text so future debugging can inspect whether the memory improved or harmed the result.

## Error Handling

- If the memory file does not exist, behave as an empty memory store.
- If one JSONL row is invalid, skip it and continue loading the remaining rows.
- If Qwen is unavailable, paste raw ASR text as before.
- If memory retrieval fails, continue without memory and log the failure.
- If a correction entry is malformed, do not send it to Qwen or Whisper.

## Testing Strategy

- Unit test memory add/list/remove behavior.
- Unit test JSONL Unicode round trips.
- Unit test malformed-row skip behavior.
- Unit test relevant memory selection for term and phrase entries.
- Unit test Qwen payload includes selected correction memory.
- Unit test Faster Whisper hotword filtering:
  - at most 5 entries
  - each entry at most 5 Unicode characters
  - duplicates removed
  - phrase corrections excluded
  - long terms excluded from Whisper but still available to Qwen
- Unit test pipeline remains fail-open when Qwen or memory retrieval fails.

## Acceptance Criteria

- `python -m pytest -q` passes.
- `python -m voicetype memory add --type term --wrong "cue and" --correct "Qwen"` stores a correction entry.
- `python -m voicetype memory list` displays stored entries.
- Dictation sends at most 5 short hotwords to Faster Whisper.
- Dictation sends relevant correction memory to Qwen.
- Qwen can repair a raw ASR mistake using correction memory.
- Qwen failure still returns or pastes raw ASR text.
- Session logs show which memory entries and Whisper hotwords were used.
