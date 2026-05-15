from collections.abc import Callable

from pynput import keyboard


RIGHT_CTRL_NAME = "ctrl_r"


class RightCtrlToggleListener:
    def __init__(self, on_toggle: Callable[[], None]) -> None:
        self.on_toggle = on_toggle
        self._listener = None

    def handle_key_release(self, key) -> None:
        if key == RIGHT_CTRL_NAME or key == keyboard.Key.ctrl_r:
            self.on_toggle()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()

    def run(self) -> None:
        with keyboard.Listener(on_release=self.handle_key_release) as listener:
            self._listener = listener
            try:
                listener.join()
            finally:
                self._listener = None
