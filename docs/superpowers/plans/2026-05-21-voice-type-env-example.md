# VoiceType Env Example Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tracked `.env-example` template so VoiceType settings can be customized through a local ignored `.env` file.

**Architecture:** Keep the existing `Settings` class unchanged because it already reads `.env` through `pydantic-settings`. Add a copyable template at the repo root, a regression test that keeps template keys aligned with `Settings`, and documentation that explains `.env-example` to `.env` usage and override priority.

**Tech Stack:** Python 3.11+, pydantic-settings, pytest, PowerShell setup commands.

---

## File Structure

- Create: `.env-example` - tracked template for common `VOICETYPE_*` settings.
- Modify: `tests/test_settings.py` - add a template drift test.
- Modify: `README.md` - document copying `.env-example` to `.env`.
- Modify: `CODEX_HANDOFF.md` - document the tracked template and ignored local override file.

---

### Task 1: Add Env Template and Drift Test

**Files:**
- Create: `.env-example`
- Modify: `tests/test_settings.py`

- [ ] **Step 1: Write the failing test**

Append this test to `tests/test_settings.py`:

```python
from pathlib import Path


def _env_example_keys() -> set[str]:
    env_example = Path(__file__).resolve().parents[1] / ".env-example"
    keys: set[str] = set()
    for line in env_example.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, separator, _value = stripped.partition("=")
        assert separator == "=", f"Invalid .env-example line: {line}"
        keys.add(key)
    return keys


def test_env_example_keys_match_settings_fields():
    keys = _env_example_keys()
    expected_keys = {
        "VOICETYPE_WHISPER_URL",
        "VOICETYPE_LLM_BASE_URL",
        "VOICETYPE_LLM_MODEL",
        "VOICETYPE_ASR_TIMEOUT_SEC",
        "VOICETYPE_LLM_TIMEOUT_SEC",
        "VOICETYPE_ENABLE_LLM",
        "VOICETYPE_SAMPLE_RATE",
        "VOICETYPE_CHANNELS",
        "VOICETYPE_RECORD_SECONDS",
        "VOICETYPE_MIN_RECORD_SECONDS",
    }

    assert expected_keys <= keys

    prefix = "VOICETYPE_"
    settings_fields = set(Settings.model_fields)
    unknown_fields = {
        key.removeprefix(prefix).lower()
        for key in keys
        if key.startswith(prefix)
    } - settings_fields

    assert unknown_fields == set()
```

- [ ] **Step 2: Run test to verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_settings.py -q
```

Expected: FAIL with `FileNotFoundError` for `.env-example`.

- [ ] **Step 3: Create `.env-example`**

Create `.env-example` at the repo root:

```dotenv
# VoiceType local settings template.
# Copy this file to .env and edit .env for this machine.
# .env is ignored by git. Direct environment variables override .env values.

VOICETYPE_WHISPER_URL=http://forge2.tail9d0481.ts.net:8008
VOICETYPE_LLM_BASE_URL=http://ai-srv.tail9d0481.ts.net:8001/v1
VOICETYPE_LLM_MODEL=qwen3.6-35b

VOICETYPE_ASR_TIMEOUT_SEC=120
VOICETYPE_LLM_TIMEOUT_SEC=20
VOICETYPE_ENABLE_LLM=true

VOICETYPE_SAMPLE_RATE=16000
VOICETYPE_CHANNELS=1
VOICETYPE_RECORD_SECONDS=8.0
VOICETYPE_MIN_RECORD_SECONDS=0.7
```

- [ ] **Step 4: Run settings tests to verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_settings.py -q
```

Expected: all settings tests pass.

- [ ] **Step 5: Commit template and test**

Run:

```powershell
git add .env-example tests/test_settings.py
git commit -m "feat: add env example template"
```

---

### Task 2: Document Env Workflow and Verify

**Files:**
- Modify: `README.md`
- Modify: `CODEX_HANDOFF.md`

- [ ] **Step 1: Update README setup**

In `README.md`, after each setup block that installs dependencies, add:

```powershell
Copy-Item .env-example .env
```

After the Python launcher setup block, add this paragraph:

```markdown
Edit `.env` to change service endpoints, timeouts, recording defaults, or whether Qwen polish is enabled. `.env` is local and ignored by git; direct `VOICETYPE_*` environment variables still override `.env` values.
```

- [ ] **Step 2: Update handoff**

In `CODEX_HANDOFF.md`, add an implemented capability bullet:

```markdown
- `.env-example` is the tracked settings template; copy it to ignored `.env` for local endpoint, timeout, recording, and LLM settings.
```

In `Common Commands`, under setup, add:

```powershell
Copy-Item .env-example .env
```

In `Useful Files`, add:

```markdown
- `.env-example` - tracked template for local `VOICETYPE_*` settings
```

In `Cautions`, add:

```markdown
- Do not commit `.env`; keep local machine-specific settings in the ignored `.env` file.
```

- [ ] **Step 3: Run verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q src tests
.\.venv\Scripts\python.exe -m voicetype --help
```

Expected:

```text
100+ tests pass
compileall exits 0
voicetype --help exits 0
```

- [ ] **Step 4: Commit documentation**

Run:

```powershell
git add README.md CODEX_HANDOFF.md
git commit -m "docs: document env settings workflow"
```

---

## Self-Review

Spec coverage:

- `.env-example` exists and uses current defaults in Task 1.
- `.env` remains ignored because `.gitignore` already contains `.env`.
- Template drift is covered by `test_env_example_keys_match_settings_fields`.
- README and handoff documentation are covered by Task 2.

Placeholder scan:

- The plan contains no unresolved placeholder markers or unspecified test steps.

Type consistency:

- `VOICETYPE_*` keys map directly to existing `Settings` fields.
- The plan does not introduce new settings fields or change env override priority.
