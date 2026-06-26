# VoiceType Settings UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved small native Settings UI for the existing VoiceType tray app.

**Architecture:** Add a JSON-backed user settings source under `%LOCALAPPDATA%\VoiceType\settings.json`, merge it below environment and `.env` overrides, and keep `Settings()` as the application-facing configuration API. Add a focused Tkinter settings window with lightweight model helpers so most behavior is unit-testable without a display. Wire the tray menu to open one settings window without changing the listener core.

**Tech Stack:** Python 3.11+, pydantic-settings, Tkinter, pytest, existing `CorrectionMemoryStore`, existing tray/startup/log helpers.

---

## File Structure

- Create: `src/voicetype/user_settings.py` - JSON path, load/save helpers, valid setting fields.
- Create: `src/voicetype/settings_ui.py` - testable UI model plus Tkinter settings window.
- Modify: `src/voicetype/settings.py` - include JSON settings as a lower-priority source than env and `.env`.
- Modify: `src/voicetype/tray.py` - add `Settings...` action and single-window opener hook.
- Add/modify tests: `tests/test_user_settings.py`, `tests/test_settings.py`, `tests/test_settings_ui.py`, `tests/test_tray.py`.
- Modify docs: `README.md`, `CODEX_HANDOFF.md`.

## Tasks

- [ ] Add failing tests for user settings path, JSON round trip, malformed-file fallback, and settings precedence.
- [ ] Implement `user_settings.py` and wire it into `Settings.settings_customise_sources()`.
- [ ] Add failing tests for the settings UI model: startup toggle callback, latest log callback, correction add/remove, and status messages.
- [ ] Implement `settings_ui.py` model helpers and Tkinter window.
- [ ] Add failing tray tests for `Settings...` wiring and single-window opener behavior.
- [ ] Wire `TrayController.open_settings()` and the tray menu item.
- [ ] Update README and handoff docs with Settings UI usage and precedence.
- [ ] Verify with focused tests, full pytest, compileall, and CLI help.

## Self-Review

- Spec coverage: covers `Settings...`, JSON persistence, env precedence, correction memory UI actions, startup toggle, log buttons, and tray runtime stability.
- Scope: does not implement richer table search, bulk import, sync, hotkey changes, installer behavior, or a new app shell.
- Testability: JSON/settings/model behavior is unit-tested without a display; manual tray verification remains required for actual Windows UI rendering.
