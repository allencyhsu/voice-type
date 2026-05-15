from collections.abc import Callable

from pynput import keyboard


RIGHT_CTRL_NAME = "ctrl_r"


class RightCtrlToggleListener:
    def __init__(self, on_toggle: Callable[[], None]) -> None:
        self.on_toggle = on_toggle

    def handle_key_release(self, key) -> None:
        if key == RIGHT_CTRL_NAME or key == keyboard.Key.ctrl_r:
            self.on_toggle()

    def run(self) -> None:
        with keyboard.Listener(on_release=self.handle_key_release) as listener:
            listener.join()
