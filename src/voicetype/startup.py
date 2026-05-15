from dataclasses import dataclass
import os
from pathlib import Path
import sys


STARTUP_FILENAME = "VoiceType.cmd"


@dataclass(frozen=True)
class StartupEntry:
    path: Path
    enabled: bool


def default_startup_dir() -> Path:
    app_data = os.environ.get("APPDATA")
    if app_data:
        return Path(app_data) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    return Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def startup_entry_path(*, startup_dir: str | Path | None = None) -> Path:
    base_dir = Path(startup_dir) if startup_dir is not None else default_startup_dir()
    return base_dir / STARTUP_FILENAME


def build_startup_command(*, python_executable: str | Path | None = None) -> str:
    executable = Path(python_executable or sys.executable)
    pythonw = executable.with_name("pythonw.exe")
    launcher = pythonw if pythonw.exists() else executable
    return f'"{launcher}" -m voicetype tray'


def enable_startup(
    *,
    startup_dir: str | Path | None = None,
    python_executable: str | Path | None = None,
) -> StartupEntry:
    path = startup_entry_path(startup_dir=startup_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'@echo off\nstart "" {build_startup_command(python_executable=python_executable)}\n',
        encoding="utf-8",
    )
    return StartupEntry(path=path, enabled=True)


def disable_startup(*, startup_dir: str | Path | None = None) -> StartupEntry:
    path = startup_entry_path(startup_dir=startup_dir)
    if path.exists():
        path.unlink()
    return StartupEntry(path=path, enabled=False)


def is_startup_enabled(*, startup_dir: str | Path | None = None) -> bool:
    return startup_entry_path(startup_dir=startup_dir).exists()
