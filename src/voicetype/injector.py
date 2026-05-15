import time

import pyautogui
import pyperclip


class TextInjector:
    def paste(self, text: str) -> None:
        pyperclip.copy(text)
        time.sleep(0.05)
        pyautogui.hotkey("ctrl", "v")
