from collections.abc import Callable
from queue import Empty, Queue
import threading


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
            bg="#111827",
            fg="#f9fafb",
            padx=20,
            pady=10,
            font=("Segoe UI", 13, "bold"),
            bd=0,
        )
        label.pack()

        hide_after_id = {"value": None}

        def show(message: str) -> None:
            label.configure(text=message)
            root.update_idletasks()
            width = root.winfo_reqwidth()
            height = root.winfo_reqheight()
            screen_width = root.winfo_screenwidth()
            x = int((screen_width - width) / 2)
            y = 48
            root.geometry(f"{width}x{height}+{x}+{y}")
            root.deiconify()
            if hide_after_id["value"] is not None:
                root.after_cancel(hide_after_id["value"])
            hide_after_id["value"] = root.after(1800, root.withdraw)

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
