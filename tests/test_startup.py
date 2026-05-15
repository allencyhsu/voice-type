from pathlib import Path

from voicetype.startup import (
    StartupEntry,
    build_startup_command,
    disable_startup,
    enable_startup,
    is_startup_enabled,
    startup_entry_path,
)


def test_startup_entry_path_uses_startup_dir():
    assert startup_entry_path(startup_dir=Path("C:/Startup")) == Path("C:/Startup/VoiceType.cmd")


def test_build_startup_command_prefers_pythonw(tmp_path):
    scripts = tmp_path / "Scripts"
    scripts.mkdir()
    pythonw = scripts / "pythonw.exe"
    pythonw.write_text("", encoding="utf-8")

    command = build_startup_command(python_executable=scripts / "python.exe")

    assert command == f'"{pythonw}" -m voicetype tray'


def test_enable_startup_writes_command_file(tmp_path):
    entry = enable_startup(
        startup_dir=tmp_path,
        python_executable=Path("C:/Project/.venv/Scripts/python.exe"),
    )

    assert entry == StartupEntry(path=tmp_path / "VoiceType.cmd", enabled=True)
    assert "voicetype tray" in entry.path.read_text(encoding="utf-8")


def test_disable_startup_removes_command_file(tmp_path):
    path = tmp_path / "VoiceType.cmd"
    path.write_text("old", encoding="utf-8")

    entry = disable_startup(startup_dir=tmp_path)

    assert entry == StartupEntry(path=path, enabled=False)
    assert not path.exists()


def test_is_startup_enabled_checks_command_file(tmp_path):
    assert is_startup_enabled(startup_dir=tmp_path) is False
    (tmp_path / "VoiceType.cmd").write_text("command", encoding="utf-8")
    assert is_startup_enabled(startup_dir=tmp_path) is True
