# VoiceType Next Iterations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve VoiceType from a working dictation MVP into a more debuggable, context-aware, and daily-usable Windows voice typing tool.

**Architecture:** Keep the CLI listener as the stable core. Add focused modules and small command surfaces around it instead of jumping straight to a tray app. Each iteration should remain independently testable and should update `CODEX_HANDOFF.md` after meaningful behavior changes.

**Tech Stack:** Python 3.11+, pytest, responses, requests, sounddevice, soundfile, pyperclip, pyautogui, ctypes Windows API, JSONL session logs.

---

## File Structure

- Modify: `src/voicetype/qwen_client.py` - add app-specific style instructions in Qwen payload/prompt.
- Modify: `tests/test_qwen_client.py` - verify style hints and app context are sent.
- Modify: `src/voicetype/cli.py` - add `logs --last`, log filters, audio diagnostic output, and smoke command wiring.
- Modify: `tests/test_cli_entrypoint.py` - parser and formatter tests for new CLI surfaces.
- Modify: `src/voicetype/session_log.py` - add helper functions for latest-record and filtered record retrieval.
- Modify: `tests/test_session_log.py` - tests for latest record and filtering helpers.
- Create: `src/voicetype/audio_diagnostics.py` - classify gain/peak/noise-level hints from session records.
- Create: `tests/test_audio_diagnostics.py` - tests for audio diagnostic rules.
- Create: `src/voicetype/smoke.py` - test harness for service and local-flow smoke checks.
- Create: `tests/test_smoke.py` - unit tests for smoke command planning and reporting.
- Modify: `README.md` - document each new user-facing command.
- Modify: `CODEX_HANDOFF.md` - keep current state, verification, and next steps aligned after each task.

---

### Task 1: App-Specific Qwen Style Hints

**Goal:** Use the active app context that is already detected in listener mode to guide Qwen polish style.

**Files:**
- Modify: `src/voicetype/qwen_client.py`
- Modify: `tests/test_qwen_client.py`
- Modify: `README.md`
- Modify: `CODEX_HANDOFF.md`

- [ ] **Step 1: Write failing test for terminal/editor app style hint**

Add to `tests/test_qwen_client.py`:

```python
@responses.activate
def test_polish_sends_app_style_hint_for_code_editors():
    responses.post(
        "http://example.test/v1/chat/completions",
        json={
            "choices": [
                {
                    "message": {
                        "content": '{"action":"insert","text":"Use pytest for this change."}'
                    }
                }
            ]
        },
        status=200,
    )

    client = QwenClient("http://example.test/v1", "qwen3.6-35b", timeout_sec=5)

    client.polish("use pytest for this change", app_name="Code")

    payload = json.loads(responses.calls[0].request.body)
    user_payload = json.loads(payload["messages"][1]["content"])
    assert user_payload["app_style_hint"] == "developer_editor"
```

- [ ] **Step 2: Run focused test and verify red**

Run:

```powershell
python -m pytest tests/test_qwen_client.py::test_polish_sends_app_style_hint_for_code_editors -q
```

Expected: FAIL because `app_style_hint` does not exist.

- [ ] **Step 3: Implement `app_style_hint_for()`**

Add to `src/voicetype/qwen_client.py`:

```python
def app_style_hint_for(app_name: str | None) -> str:
    normalized = (app_name or "").lower()
    if normalized in {"code", "cursor", "windsurf", "pycharm", "webstorm"}:
        return "developer_editor"
    if normalized in {"windowsterminal", "powershell", "cmd", "conhost"}:
        return "terminal"
    if normalized in {"chrome", "msedge", "firefox", "brave"}:
        return "browser"
    if normalized in {"notepad", "winword", "onenote"}:
        return "prose_editor"
    return "general"
```

- [ ] **Step 4: Add style hint to Qwen user payload**

In `QwenClient.polish()`, extend `user_payload`:

```python
"app_style_hint": app_style_hint_for(app_name),
```

- [ ] **Step 5: Add explicit prompt rule for style hints**

In `SYSTEM_PROMPT`, add:

```text
- Use app_style_hint only to tune formatting style; do not add content or change meaning.
- For developer_editor and terminal, keep commands, code identifiers, flags, paths, and error text literal.
- For prose_editor and browser, prefer clean natural punctuation.
```

- [ ] **Step 6: Run Qwen tests**

Run:

```powershell
python -m pytest tests/test_qwen_client.py -q
```

Expected: all Qwen tests pass.

- [ ] **Step 7: Update docs**

Add a short note to `README.md` under the Qwen polish section:

```markdown
VoiceType passes the focused app name and a small style hint to Qwen. Developer editors and terminals preserve commands, file paths, flags, and code identifiers more conservatively.
```

- [ ] **Step 8: Full verification**

Run:

```powershell
python -m pytest -q
python -m compileall -q src tests
```

Expected:

```text
all tests passed
compileall OK
```

- [ ] **Step 9: Commit**

Run:

```powershell
git add src/voicetype/qwen_client.py tests/test_qwen_client.py README.md CODEX_HANDOFF.md
git commit -m "feat: add app-specific Qwen style hints"
git push origin feature/voice-type-mvp
```

---

### Task 2: Faster Log Triage Commands

**Goal:** Make it easier to inspect the latest session without repeatedly using `--limit 5 --json`.

**Files:**
- Modify: `src/voicetype/session_log.py`
- Modify: `src/voicetype/cli.py`
- Modify: `tests/test_session_log.py`
- Modify: `tests/test_cli_entrypoint.py`
- Modify: `README.md`
- Modify: `CODEX_HANDOFF.md`

- [ ] **Step 1: Write failing test for latest record helper**

Add to `tests/test_session_log.py`:

```python
def test_latest_session_record_returns_most_recent_record(tmp_path):
    log_path = tmp_path / "2026-05-15.jsonl"
    log_path.write_text(
        '{"completed_at":"2026-05-15T09:00:00+08:00"}\n'
        '{"completed_at":"2026-05-15T09:10:00+08:00"}\n',
        encoding="utf-8",
    )

    record = latest_session_record(day=date(2026, 5, 15), log_dir=tmp_path)

    assert record == {"completed_at": "2026-05-15T09:10:00+08:00"}
```

- [ ] **Step 2: Run focused test and verify red**

Run:

```powershell
python -m pytest tests/test_session_log.py::test_latest_session_record_returns_most_recent_record -q
```

Expected: FAIL because `latest_session_record` does not exist.

- [ ] **Step 3: Implement helper**

In `src/voicetype/session_log.py`, add:

```python
def latest_session_record(*, day: date | None = None, log_dir: str | Path | None = None) -> dict[str, Any] | None:
    records = read_session_records(day=day, log_dir=log_dir)
    if not records:
        return None
    return records[-1]
```

- [ ] **Step 4: Add parser test for `logs --last`**

Add to `tests/test_cli_entrypoint.py`:

```python
def test_logs_parser_accepts_last_flag():
    parser = build_parser()

    args = parser.parse_args(["logs", "--last", "--json"])

    assert args.command == "logs"
    assert args.last is True
    assert args.json is True
```

- [ ] **Step 5: Run parser test and verify red**

Run:

```powershell
python -m pytest tests/test_cli_entrypoint.py::test_logs_parser_accepts_last_flag -q
```

Expected: FAIL because `--last` is not defined.

- [ ] **Step 6: Add `--last` parser option**

In `build_parser()` under `logs_parser`, add:

```python
logs_parser.add_argument("--last", action="store_true")
```

- [ ] **Step 7: Implement `run_logs()` last-record branch**

In `run_logs(args)`, before the normal summary branch:

```python
if args.last:
    record = latest_session_record(day=day, log_dir=log_dir)
    if record is None:
        print(f"[VoiceType] No session log found for today: {path}")
        return
    if args.json:
        print(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
        return
    print(format_log_record(record))
    return
```

- [ ] **Step 8: Update imports**

In `src/voicetype/cli.py`, import:

```python
latest_session_record
```

from `voicetype.session_log`.

- [ ] **Step 9: Run focused tests**

Run:

```powershell
python -m pytest tests/test_session_log.py tests/test_cli_entrypoint.py -q
```

Expected: pass.

- [ ] **Step 10: Manual no-log smoke**

Run:

```powershell
$env:LOCALAPPDATA = Join-Path $PWD ".tmp-localappdata"
python -m voicetype logs --last
python -m voicetype logs --last --json
```

Expected: both commands print a friendly no-log message and exit successfully.

- [ ] **Step 11: Update docs**

Add to `README.md`:

```markdown
Show only the latest segment:

```powershell
python -m voicetype logs --last
python -m voicetype logs --last --json
```
```

- [ ] **Step 12: Full verification and commit**

Run:

```powershell
python -m pytest -q
python -m compileall -q src tests
python -m voicetype logs --help
git add src/voicetype/session_log.py src/voicetype/cli.py tests/test_session_log.py tests/test_cli_entrypoint.py README.md CODEX_HANDOFF.md
git commit -m "feat: add latest session log command"
git push origin feature/voice-type-mvp
```

Expected: tests pass, help includes `--last`, push succeeds.

---

### Task 3: Audio Quality Diagnostics

**Goal:** Turn repeated `gain=50.0x` and low peak observations into actionable diagnostics.

**Files:**
- Create: `src/voicetype/audio_diagnostics.py`
- Create: `tests/test_audio_diagnostics.py`
- Modify: `src/voicetype/cli.py`
- Modify: `tests/test_cli_entrypoint.py`
- Modify: `README.md`
- Modify: `CODEX_HANDOFF.md`

- [ ] **Step 1: Write failing tests for diagnostic classification**

Create `tests/test_audio_diagnostics.py`:

```python
from voicetype.audio_diagnostics import classify_audio_record


def test_classify_audio_record_flags_gain_ceiling():
    record = {
        "audio": {"seconds": 4.0},
        "normalization": {
            "applied": True,
            "gain": 50.0,
            "peak_before": 0.009,
            "peak_after": 0.45,
        },
    }

    assert classify_audio_record(record) == [
        "input_level_low: normalization hit 50.0x gain ceiling"
    ]


def test_classify_audio_record_returns_empty_when_level_is_healthy():
    record = {
        "audio": {"seconds": 4.0},
        "normalization": {
            "applied": False,
            "gain": 1.0,
            "peak_before": 0.25,
            "peak_after": 0.25,
        },
    }

    assert classify_audio_record(record) == []
```

- [ ] **Step 2: Run tests and verify red**

Run:

```powershell
python -m pytest tests/test_audio_diagnostics.py -q
```

Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement classifier**

Create `src/voicetype/audio_diagnostics.py`:

```python
from typing import Any


def classify_audio_record(record: dict[str, Any]) -> list[str]:
    messages: list[str] = []
    normalization = record.get("normalization") or {}
    gain = normalization.get("gain")
    peak_before = normalization.get("peak_before")

    if isinstance(gain, int | float) and gain >= 50.0:
        messages.append("input_level_low: normalization hit 50.0x gain ceiling")
    elif isinstance(peak_before, int | float) and peak_before < 0.03:
        messages.append("input_level_low: captured peak is below 0.03")

    return messages
```

- [ ] **Step 4: Run diagnostic tests**

Run:

```powershell
python -m pytest tests/test_audio_diagnostics.py -q
```

Expected: pass.

- [ ] **Step 5: Add CLI parser test for `logs --diagnose`**

Add to `tests/test_cli_entrypoint.py`:

```python
def test_logs_parser_accepts_diagnose_flag():
    parser = build_parser()

    args = parser.parse_args(["logs", "--today", "--diagnose"])

    assert args.diagnose is True
```

- [ ] **Step 6: Add parser option**

In `build_parser()`:

```python
logs_parser.add_argument("--diagnose", action="store_true")
```

- [ ] **Step 7: Add diagnostic output in `run_logs()`**

Import:

```python
from voicetype.audio_diagnostics import classify_audio_record
```

When `args.diagnose` is true, after each summary line print each diagnostic:

```python
if args.diagnose:
    for diagnostic in classify_audio_record(record):
        print(f"  diagnostic: {diagnostic}")
```

- [ ] **Step 8: Run focused tests**

Run:

```powershell
python -m pytest tests/test_audio_diagnostics.py tests/test_cli_entrypoint.py -q
```

Expected: pass.

- [ ] **Step 9: Manual smoke with current logs**

Run:

```powershell
python -m voicetype logs --today --limit 3 --diagnose
```

Expected: recent records with `gain=50.0` show `input_level_low`.

- [ ] **Step 10: Update docs and handoff**

Document:

```powershell
python -m voicetype logs --today --limit 5 --diagnose
```

Explain that this is a diagnostic hint, not an automatic fix.

- [ ] **Step 11: Full verification and commit**

Run:

```powershell
python -m pytest -q
python -m compileall -q src tests
git add src/voicetype/audio_diagnostics.py tests/test_audio_diagnostics.py src/voicetype/cli.py tests/test_cli_entrypoint.py README.md CODEX_HANDOFF.md
git commit -m "feat: add audio diagnostics for session logs"
git push origin feature/voice-type-mvp
```

---

### Task 4: Local Smoke Command

**Goal:** Provide a reproducible command that verifies local CLI wiring without requiring manual hotkey use.

**Files:**
- Create: `src/voicetype/smoke.py`
- Create: `tests/test_smoke.py`
- Modify: `src/voicetype/cli.py`
- Modify: `tests/test_cli_entrypoint.py`
- Modify: `README.md`
- Modify: `CODEX_HANDOFF.md`

- [ ] **Step 1: Write smoke report test**

Create `tests/test_smoke.py`:

```python
from voicetype.smoke import SmokeReport


def test_smoke_report_formats_checks():
    report = SmokeReport(
        checks=[
            ("settings", True, "loaded"),
            ("logs", True, "available"),
            ("active_app", True, "Code"),
        ]
    )

    assert report.lines() == [
        "[ok] settings: loaded",
        "[ok] logs: available",
        "[ok] active_app: Code",
    ]
```

- [ ] **Step 2: Run smoke test and verify red**

Run:

```powershell
python -m pytest tests/test_smoke.py -q
```

Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement `SmokeReport`**

Create `src/voicetype/smoke.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class SmokeReport:
    checks: list[tuple[str, bool, str]]

    def lines(self) -> list[str]:
        return [
            f"[{'ok' if passed else 'fail'}] {name}: {message}"
            for name, passed, message in self.checks
        ]
```

- [ ] **Step 4: Add parser test for `smoke`**

Add to `tests/test_cli_entrypoint.py`:

```python
def test_cli_has_smoke_command():
    parser = build_parser()

    args = parser.parse_args(["smoke"])

    assert args.command == "smoke"
```

- [ ] **Step 5: Add CLI command**

In `build_parser()`:

```python
smoke_parser = subparsers.add_parser("smoke")
smoke_parser.set_defaults(command="smoke")
```

- [ ] **Step 6: Implement `run_smoke()`**

In `src/voicetype/cli.py`, add:

```python
def run_smoke() -> None:
    report = SmokeReport(
        checks=[
            ("settings", True, "loaded"),
            ("logs", True, str(default_log_dir())),
            ("active_app", True, get_active_app_name()),
        ]
    )
    for line in report.lines():
        print(line)
```

And in `main()` before service initialization:

```python
if args.command == "smoke":
    run_smoke()
    return
```

- [ ] **Step 7: Run focused tests**

Run:

```powershell
python -m pytest tests/test_smoke.py tests/test_cli_entrypoint.py -q
```

Expected: pass.

- [ ] **Step 8: Manual smoke**

Run:

```powershell
python -m voicetype smoke
```

Expected output shape:

```text
[ok] settings: loaded
[ok] logs: C:\Users\Allen\AppData\Local\VoiceType\logs
[ok] active_app: <current app or unknown>
```

- [ ] **Step 9: Update docs and commit**

Run:

```powershell
python -m pytest -q
python -m compileall -q src tests
git add src/voicetype/smoke.py tests/test_smoke.py src/voicetype/cli.py tests/test_cli_entrypoint.py README.md CODEX_HANDOFF.md
git commit -m "feat: add local smoke command"
git push origin feature/voice-type-mvp
```

---

### Task 5: Tray App Readiness Checklist

**Goal:** Prepare for tray/background mode without prematurely replacing the working CLI listener.

**Files:**
- Create: `docs/tray-readiness.md`
- Modify: `README.md`
- Modify: `CODEX_HANDOFF.md`

- [ ] **Step 1: Create readiness doc**

Create `docs/tray-readiness.md`:

```markdown
# Tray App Readiness

## Current CLI contracts that must remain stable

- `python -m voicetype listen`
- Right Alt starts and stops recording.
- The microphone is only open while actively recording.
- Overlay remains visible while listening.
- Logs are written to `%LOCALAPPDATA%\VoiceType\logs\YYYY-MM-DD.jsonl`.

## Tray MVP requirements

- Start and stop listener without a terminal window.
- Show current status in the tray menu.
- Keep the top-most overlay behavior.
- Provide menu actions:
  - Open logs directory
  - Show latest log
  - Quit VoiceType
- Use the same listener core as CLI mode.

## Not in tray MVP

- Installer
- Auto update
- Account login
- Cloud sync
- Long-term audio library
```

- [ ] **Step 2: Add README note**

Add:

```markdown
Tray mode is not implemented yet. The current plan is to keep the CLI listener as the stable core and wrap it after logging, diagnostics, and smoke checks are reliable.
```

- [ ] **Step 3: Update handoff next steps**

In `CODEX_HANDOFF.md`, keep tray work after diagnostics and smoke checks.

- [ ] **Step 4: Verify docs**

Run:

```powershell
git diff --check
```

Expected: no output.

- [ ] **Step 5: Commit**

Run:

```powershell
git add docs/tray-readiness.md README.md CODEX_HANDOFF.md
git commit -m "docs: add tray readiness checklist"
git push origin feature/voice-type-mvp
```

---

## Final Verification After All Tasks

- [ ] Run tests:

```powershell
python -m pytest -q
```

- [ ] Compile Python files:

```powershell
python -m compileall -q src tests
```

- [ ] Check CLI help:

```powershell
python -m voicetype --help
python -m voicetype listen --help
python -m voicetype logs --help
python -m voicetype smoke
```

- [ ] Check latest log:

```powershell
python -m voicetype logs --last
python -m voicetype logs --last --json
```

- [ ] Confirm clean worktree:

```powershell
git status --short --branch
```

- [ ] Push final branch state:

```powershell
git push origin feature/voice-type-mvp
```

---

## Self-Review

Spec coverage:

- App context is already detected; Task 1 uses it to improve Qwen behavior.
- Session logs already exist; Task 2 and Task 3 make them faster to inspect and more actionable.
- Testing is currently manual through listener mode; Task 4 adds a stable local smoke command.
- Tray app is a future shell; Task 5 prevents premature tray work before CLI contracts are stable.

Placeholder scan:

- No `TBD`, `TODO`, or vague implementation instructions remain.
- Each task includes file paths, commands, and expected outcomes.

Type consistency:

- `app_name` remains the shared field name across active window detection, Qwen payload, and session logs.
- Log records remain `dict[str, Any]`.
- CLI commands stay under `python -m voicetype`.
