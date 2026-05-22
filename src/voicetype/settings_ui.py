from __future__ import annotations

from collections.abc import Callable
import os
from pathlib import Path
import threading
from queue import Empty, Queue
from typing import Any

from voicetype.memory import CorrectionEntry, CorrectionMemoryStore, CorrectionType
from voicetype.settings import Settings
from voicetype.startup import disable_startup, enable_startup, is_startup_enabled
from voicetype.user_settings import USER_SETTING_FIELDS, load_user_settings, save_user_settings


CONFIGURABLE_SETTING_FIELDS = (
    "whisper_url",
    "llm_base_url",
    "llm_model",
    "enable_llm",
    "notify",
    "record_seconds",
    "min_record_seconds",
)
NOTIFY_MODES = {"overlay", "console", "toast", "off"}


class SettingsUiModel:
    def __init__(
        self,
        *,
        settings_path: str | Path | None = None,
        settings_factory: Callable[[], Settings] = Settings,
        memory_store: CorrectionMemoryStore | None = None,
        startup_enabled: Callable[[], bool] = is_startup_enabled,
        enable_startup: Callable[[], object] = enable_startup,
        disable_startup: Callable[[], object] = disable_startup,
        open_logs: Callable[[], object] | None = None,
        show_latest_log: Callable[[], object] | None = None,
    ) -> None:
        self.settings_path = Path(settings_path) if settings_path is not None else None
        self.settings_factory = settings_factory
        self.memory_store = memory_store or CorrectionMemoryStore()
        self.startup_enabled = startup_enabled
        self.enable_startup = enable_startup
        self.disable_startup = disable_startup
        self._open_logs = open_logs or open_logs_directory
        self._show_latest_log = show_latest_log or open_latest_log_file

    def load_settings(self) -> tuple[dict[str, Any], str | None]:
        load_result = load_user_settings(path=self.settings_path, allowed_fields=USER_SETTING_FIELDS)
        settings = self.settings_factory()
        values = {
            field_name: getattr(settings, field_name)
            for field_name in CONFIGURABLE_SETTING_FIELDS
        }
        return values, load_result.error

    def save_settings(self, values: dict[str, Any]) -> str:
        try:
            coerced = coerce_settings_values(values)
            existing = load_user_settings(path=self.settings_path, allowed_fields=USER_SETTING_FIELDS).values
            existing.update(coerced)
            save_user_settings(
                existing,
                path=self.settings_path,
                allowed_fields=USER_SETTING_FIELDS,
            )
        except (OSError, TypeError, ValueError) as exc:
            return str(exc)
        return "Saved. Restart VoiceType for all settings to take effect."

    def is_startup_enabled(self) -> bool:
        return self.startup_enabled()

    def set_startup_enabled(self, enabled: bool) -> str:
        try:
            if enabled:
                self.enable_startup()
                return "Start at login enabled."
            self.disable_startup()
            return "Start at login disabled."
        except OSError as exc:
            return f"Could not update start at login: {exc}"

    def open_logs(self) -> str:
        try:
            self._open_logs()
        except OSError as exc:
            return f"Could not open logs: {exc}"
        return "Opened logs."

    def show_latest_log(self) -> str:
        try:
            self._show_latest_log()
        except OSError as exc:
            return f"Could not open latest log: {exc}"
        return "Opened latest log."

    def load_corrections(self) -> list[CorrectionEntry]:
        return self.memory_store.load()

    def add_correction(self, entry_type: str, *, wrong: str, correct: str) -> CorrectionEntry:
        return self.memory_store.add(CorrectionType(entry_type), wrong=wrong, correct=correct)

    def remove_correction(self, entry_id: str) -> str:
        removed = self.memory_store.remove(entry_id)
        if removed:
            return "Removed correction memory entry."
        return "No correction memory entry found."


def coerce_settings_values(values: dict[str, Any]) -> dict[str, Any]:
    coerced: dict[str, Any] = {}
    for field_name in CONFIGURABLE_SETTING_FIELDS:
        if field_name not in values:
            continue
        value = values[field_name]
        if field_name in {"whisper_url", "llm_base_url", "llm_model"}:
            text = str(value).strip()
            if not text:
                raise ValueError(f"{field_name} cannot be empty")
            coerced[field_name] = text
            continue
        if field_name == "enable_llm":
            coerced[field_name] = coerce_bool(value)
            continue
        if field_name == "notify":
            notify = str(value).strip()
            if notify not in NOTIFY_MODES:
                raise ValueError(f"Unsupported notification mode: {notify}")
            coerced[field_name] = notify
            continue
        if field_name in {"record_seconds", "min_record_seconds"}:
            number = float(value)
            if number <= 0:
                raise ValueError(f"{field_name} must be greater than 0")
            coerced[field_name] = number
    return coerced


def coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Unsupported boolean value: {value}")


def open_logs_directory() -> None:
    from voicetype.session_log import default_log_dir

    log_dir = default_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    os.startfile(log_dir)


def open_latest_log_file() -> None:
    from voicetype.tray import latest_log_text, show_latest_log_file

    show_latest_log_file("VoiceType Latest Log", latest_log_text())


class SettingsWindow:
    def __init__(self, root, *, model: SettingsUiModel | None = None) -> None:
        self.root = root
        self.model = model or SettingsUiModel()
        self.memory_entries: list[CorrectionEntry] = []
        self.setting_vars: dict[str, Any] = {}
        self.status_var = None
        self.memory_list = None
        self.memory_type_var = None
        self.memory_wrong_var = None
        self.memory_correct_var = None
        self.startup_var = None
        self._build()
        self.refresh()

    def _build(self) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.root.title("VoiceType Settings")
        self.root.attributes("-topmost", True)
        self.root.geometry("620x620")
        self.root.minsize(560, 520)

        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)

        services = ttk.LabelFrame(outer, text="Services", padding=8)
        services.grid(row=0, column=0, sticky="ew")
        services.columnconfigure(1, weight=1)
        self._entry(services, 0, "Faster Whisper URL", "whisper_url")
        self._entry(services, 1, "Qwen base URL", "llm_base_url")
        self._entry(services, 2, "Qwen model", "llm_model")
        self.setting_vars["enable_llm"] = tk.BooleanVar()
        ttk.Checkbutton(
            services,
            text="Enable Qwen polish",
            variable=self.setting_vars["enable_llm"],
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))

        dictation = ttk.LabelFrame(outer, text="Dictation", padding=8)
        dictation.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        dictation.columnconfigure(1, weight=1)
        self.setting_vars["notify"] = tk.StringVar()
        ttk.Label(dictation, text="Notification mode").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            dictation,
            textvariable=self.setting_vars["notify"],
            values=("overlay", "console", "toast", "off"),
            state="readonly",
        ).grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self._entry(dictation, 1, "Record seconds", "record_seconds")
        self._entry(dictation, 2, "Minimum recording seconds", "min_record_seconds")
        ttk.Label(dictation, text="Hotkey: Right Ctrl").grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))

        diagnostics = ttk.LabelFrame(outer, text="Startup and diagnostics", padding=8)
        diagnostics.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.startup_var = tk.BooleanVar()
        ttk.Checkbutton(
            diagnostics,
            text="Start at login",
            variable=self.startup_var,
            command=self._on_startup_toggle,
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(diagnostics, text="Open Logs", command=self._on_open_logs).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(diagnostics, text="Show Latest Log", command=self._on_show_latest_log).grid(row=0, column=2, padx=(8, 0))

        memory = ttk.LabelFrame(outer, text="Correction memory", padding=8)
        memory.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        outer.rowconfigure(3, weight=1)
        memory.columnconfigure(0, weight=1)
        self.memory_list = tk.Listbox(memory, height=7)
        self.memory_list.grid(row=0, column=0, columnspan=4, sticky="nsew")
        self.memory_type_var = tk.StringVar(value="term")
        self.memory_wrong_var = tk.StringVar()
        self.memory_correct_var = tk.StringVar()
        ttk.Combobox(
            memory,
            textvariable=self.memory_type_var,
            values=("term", "phrase"),
            width=8,
            state="readonly",
        ).grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Entry(memory, textvariable=self.memory_wrong_var).grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Entry(memory, textvariable=self.memory_correct_var).grid(row=1, column=2, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Button(memory, text="Add", command=self._on_add_correction).grid(row=1, column=3, padx=(8, 0), pady=(8, 0))
        ttk.Button(memory, text="Remove Selected", command=self._on_remove_correction).grid(row=2, column=0, sticky="w", pady=(8, 0))
        memory.columnconfigure(1, weight=1)
        memory.columnconfigure(2, weight=1)

        actions = ttk.Frame(outer)
        actions.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        actions.columnconfigure(0, weight=1)
        self.status_var = tk.StringVar()
        ttk.Label(actions, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Button(actions, text="Save", command=self._on_save).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(actions, text="Close", command=self.root.destroy).grid(row=0, column=2, padx=(8, 0))

    def _entry(self, parent, row: int, label: str, field_name: str) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.setting_vars[field_name] = tk.StringVar()
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(parent, textvariable=self.setting_vars[field_name]).grid(
            row=row,
            column=1,
            sticky="ew",
            padx=(8, 0),
            pady=(4, 0),
        )

    def refresh(self) -> None:
        values, error = self.model.load_settings()
        for field_name, value in values.items():
            variable = self.setting_vars.get(field_name)
            if variable is not None:
                variable.set(value)
        if self.startup_var is not None:
            self.startup_var.set(self.model.is_startup_enabled())
        self.refresh_memory()
        if self.status_var is not None:
            self.status_var.set(error or "")

    def refresh_memory(self) -> None:
        if self.memory_list is None:
            return
        self.memory_entries = self.model.load_corrections()
        self.memory_list.delete(0, "end")
        for entry in self.memory_entries:
            self.memory_list.insert("end", f"{entry.type.value}: {entry.wrong} -> {entry.correct}")

    def _form_values(self) -> dict[str, Any]:
        return {
            field_name: variable.get()
            for field_name, variable in self.setting_vars.items()
        }

    def _set_status(self, message: str) -> None:
        if self.status_var is not None:
            self.status_var.set(message)

    def _on_save(self) -> None:
        self._set_status(self.model.save_settings(self._form_values()))

    def _on_startup_toggle(self) -> None:
        self._set_status(self.model.set_startup_enabled(bool(self.startup_var.get())))

    def _on_open_logs(self) -> None:
        self._set_status(self.model.open_logs())

    def _on_show_latest_log(self) -> None:
        self._set_status(self.model.show_latest_log())

    def _on_add_correction(self) -> None:
        try:
            self.model.add_correction(
                self.memory_type_var.get(),
                wrong=self.memory_wrong_var.get(),
                correct=self.memory_correct_var.get(),
            )
        except ValueError as exc:
            self._set_status(str(exc))
            return
        self.memory_wrong_var.set("")
        self.memory_correct_var.set("")
        self.refresh_memory()
        self._set_status("Added correction memory entry.")

    def _on_remove_correction(self) -> None:
        selected = self.memory_list.curselection()
        if not selected:
            self._set_status("No correction memory entry selected.")
            return
        entry = self.memory_entries[selected[0]]
        self._set_status(self.model.remove_correction(entry.id))
        self.refresh_memory()


class TkSettingsWindowHandle:
    def __init__(self, *, model: SettingsUiModel | None = None) -> None:
        self.model = model
        self._queue: Queue[str] = Queue()
        self._thread = threading.Thread(target=self._run, name="voicetype-settings", daemon=True)
        self._thread.start()

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def focus(self) -> None:
        self._queue.put("focus")

    def _run(self) -> None:
        import tkinter as tk

        root = tk.Tk()
        window = SettingsWindow(root, model=self.model)

        def poll() -> None:
            try:
                while True:
                    command = self._queue.get_nowait()
                    if command == "focus":
                        root.deiconify()
                        root.lift()
                        root.focus_force()
            except Empty:
                pass
            root.after(100, poll)

        root.after(100, poll)
        root.mainloop()


_settings_window_handle: TkSettingsWindowHandle | None = None


def open_settings_window() -> None:
    global _settings_window_handle
    if _settings_window_handle is not None and _settings_window_handle.is_alive():
        _settings_window_handle.focus()
        return
    _settings_window_handle = TkSettingsWindowHandle()
