import tkinter as tk
from pynput import keyboard
from screeninfo import get_monitors
import ctypes
import importlib

from fastshot.snipping_tool import SnippingTool
from fastshot.image_window import ImageWindow

class SnipasteApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.monitors = get_monitors()
        self.snipping_tool = SnippingTool(self.root, self.monitors, self.on_screenshot)
        self.windows = []
        self.plugins = {}
        self.load_plugins()
        self.setup_hotkey_listener()

    def load_plugins(self):
        plugin_modules = ['fastshot.plugin_ocr']  # 可以在此添加更多插件模块
        for module_name in plugin_modules:
            module = importlib.import_module(module_name)
            plugin_class = getattr(module, 'PluginOCR')
            self.plugins[module_name] = plugin_class()

    def setup_hotkey_listener(self):
        def on_activate_snip():
            print("Hotkey activated")
            self.snipping_tool.start_snipping()

        def on_escape():
            self.exit_all_modes()

        def for_canonical(f):
            return lambda k: f(self.listener.canonical(k))

        hotkey_snip = keyboard.HotKey(keyboard.HotKey.parse('<f1>'), on_activate_snip)
        
        ctypes.windll.user32.RegisterHotKey(None, 1, 0, 0x70)  # 0x70 is the virtual key code for F1

        self.listener = keyboard.Listener(
            on_press=for_canonical(hotkey_snip.press),
            on_release=for_canonical(hotkey_snip.release))
        
        self.listener.start()

        self.listener_escape = keyboard.Listener(
            on_press=for_canonical(lambda key: on_escape() if key == keyboard.Key.esc else None))
        
        self.listener_escape.start()

    def on_screenshot(self, img):
        window = ImageWindow(self, img)
        self.windows.append(window)

    def exit_all_modes(self):
        for window in self.windows:
            if window.img_window.winfo_exists():  # 检查窗口是否存在
                window.exit_edit_mode()

    def run(self):
        self.root.mainloop()

def main():
    app = SnipasteApp()
    app.run()

if __name__ == "__main__":
    main()
