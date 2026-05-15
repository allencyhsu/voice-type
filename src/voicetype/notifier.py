from collections.abc import Callable
from dataclasses import dataclass
from queue import Empty, Queue
import threading


@dataclass(frozen=True)
class OverlayPresentation:
    bg: str
    fg: str
    hide_after_ms: int | None


def overlay_presentation_for(message: str) -> OverlayPresentation:
    normalized = message.lower()
    if "listening" in normalized:
        return OverlayPresentation(bg="#dc2626", fg="#fff7ed", hide_after_ms=None)
    if "processing" in normalized:
        return OverlayPresentation(bg="#f59e0b", fg="#1f2937", hide_after_ms=1800)
    if "inserted" in normalized:
        return OverlayPresentation(bg="#16a34a", fg="#ecfdf5", hide_after_ms=1800)
    if "ignored" in normalized or "no text" in normalized:
        return OverlayPresentation(bg="#7c3aed", fg="#f5f3ff", hide_after_ms=2400)
    return OverlayPresentation(bg="#2563eb", fg="#eff6ff", hide_after_ms=1800)


def overlay_geometry(
    *,
    width: int,
    height: int,
    screen_width: int,
    screen_height: int,
    bottom_margin: int = 88,
) -> tuple[int, int]:
    x = max(0, int((screen_width - width) / 2))
    y = max(0, screen_height - height - bottom_margin)
    return x, y


class ConsoleNotifier:
    def notify(self, message: str) -> None:
        print(f"[VoiceType] {message}")


class NullNotifier:
    def notify(self, message: str) -> None:
        return


class ToastNotifier:
    def __init__(self, *, toast_factory: Callable | None = None) -> None:
        self.toast_factory = toast_factory

    def notify(self, message: str) -> None:
        toast_factory = self.toast_factory or _load_toast_factory()
        toast = toast_factory(
            app_id="VoiceType",
            title="VoiceType",
            msg=message,
            duration="short",
        )
        toast.show()


class OverlayNotifier:
    def __init__(self, *, overlay_factory: Callable | None = None) -> None:
        self.overlay_factory = overlay_factory or TkOverlayBackend
        self._overlay = None

    def notify(self, message: str) -> None:
        if is_diagnostic_message(message):
            return
        if self._overlay is None:
            self._overlay = self.overlay_factory()
        self._overlay.notify(message)


def create_notifier(mode: str):
    if mode == "console":
        return ConsoleNotifier()
    if mode == "overlay":
        return OverlayNotifier()
    if mode == "toast":
        return ToastNotifier()
    if mode == "off":
        return NullNotifier()
    raise ValueError(f"Unsupported notifier mode: {mode}")


def is_diagnostic_message(message: str) -> bool:
    normalized = message.lower()
    return normalized.startswith("captured ") or normalized.startswith("normalized audio ")


def _load_toast_factory():
    from winotify import Notification

    return Notification


class TkOverlayBackend:
    def __init__(self) -> None:
        self._queue: Queue[str] = Queue()
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, name="voicetype-overlay", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=2)

    def notify(self, message: str) -> None:
        self._queue.put(message)

    def _run(self) -> None:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.92)
        try:
            root.attributes("-disabled", True)
        except tk.TclError:
            pass

        label = tk.Label(
            root,
            bg="#dc2626",
            fg="#fff7ed",
            padx=24,
            pady=12,
            font=("Segoe UI", 14, "bold"),
            bd=0,
        )
        label.pack()

        hide_after_id = {"value": None}

        def show(message: str) -> None:
            presentation = overlay_presentation_for(message)
            root.configure(bg=presentation.bg)
            label.configure(text=message, bg=presentation.bg, fg=presentation.fg)
            root.update_idletasks()
            width = root.winfo_reqwidth()
            height = root.winfo_reqheight()
            screen_width = root.winfo_screenwidth()
            screen_height = root.winfo_screenheight()
            x, y = overlay_geometry(
                width=width,
                height=height,
                screen_width=screen_width,
                screen_height=screen_height,
            )
            root.geometry(f"{width}x{height}+{x}+{y}")
            root.deiconify()
            if hide_after_id["value"] is not None:
                root.after_cancel(hide_after_id["value"])
                hide_after_id["value"] = None
            if presentation.hide_after_ms is not None:
                hide_after_id["value"] = root.after(presentation.hide_after_ms, root.withdraw)

        def poll() -> None:
            try:
                while True:
                    show(self._queue.get_nowait())
            except Empty:
                pass
            root.after(50, poll)

        self._ready.set()
        root.after(50, poll)
        root.mainloop()
