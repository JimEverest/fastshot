# window_control.py

import ctypes
from ctypes import wintypes
from pynput import keyboard
import win32gui
import win32con
import win32process
import time

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Constants
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x80000
LWA_ALPHA = 0x2

# Global variable for window opacity
current_window_opacity = 1.0  # Default opacity

def get_foreground_window():
    hwnd = user32.GetForegroundWindow()
    if hwnd and user32.IsWindow(hwnd) and user32.IsWindowVisible(hwnd):
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        process_handle = open_process(pid)
        if process_handle:
            executable = win32process.GetModuleFileNameEx(process_handle, None)
            window_title = win32gui.GetWindowText(hwnd)
            window_class = win32gui.GetClassName(hwnd)
            print(f"Current active window handle: {hwnd}, Title: {window_title}, Executable: {executable}, Class: {window_class}")
            return hwnd
        else:
            print(f"Cannot open process, PID: {pid}")
            return None
    else:
        print("Cannot get valid foreground window handle or window is not visible")
        return None

def open_process(pid):
    PROCESS_ALL_ACCESS = (0x000F0000 | 0x00100000 | 0xFFF)
    return kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)

def set_window_opacity(hwnd, opacity):
    global current_window_opacity
    if hwnd:
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)
        # Ensure opacity is between 10% and 100%
        opacity = max(0.1, min(opacity, 1.0))
        current_window_opacity = opacity
        print(f"Setting opacity: {opacity * 100}%")
        user32.SetLayeredWindowAttributes(hwnd, 0, int(255 * opacity), LWA_ALPHA)

def get_window_opacity(hwnd):
    global current_window_opacity
    return current_window_opacity

def toggle_always_on_top():
    hwnd = get_foreground_window()
    if hwnd == 0:
        return
    window_title = win32gui.GetWindowText(hwnd)

    try:
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        is_topmost = bool(ex_style & win32con.WS_EX_TOPMOST)

        if is_topmost:
            # Remove always-on-top
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_NOTOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
            )
            print(f"Window '{window_title}' is no longer always on top.")
        else:
            # Set always-on-top
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
            )
            print(f"Window '{window_title}' is now always on top.")
    except Exception as e:
        print(f"Exception while toggling always-on-top: {e}")

class HotkeyListener:
    def __init__(self, config, root, app):
        self.config = config
        self.root = root  # Tkinter root window
        self.app = app  # Reference to main application
        self.load_hotkeys()
        self.listener = None
        self.ctrl_press_count = 0
        self.ctrl_last_release_time = 0.0

    def load_hotkeys(self):
        shortcuts = self.config['Shortcuts']

        # Load standard hotkeys
        self.hotkey_topmost_on = keyboard.HotKey(
            keyboard.HotKey.parse(shortcuts.get('hotkey_topmost_on', '<ctrl>+<shift>+t')),
            self.toggle_topmost_on
        )
        self.hotkey_topmost_off = keyboard.HotKey(
            keyboard.HotKey.parse(shortcuts.get('hotkey_topmost_off', '<ctrl>+<shift>+r')),
            self.toggle_topmost_off
        )
        self.hotkey_opacity_down = keyboard.HotKey(
            keyboard.HotKey.parse(shortcuts.get('hotkey_opacity_down', '<ctrl>+<shift>+[')),
            self.decrease_opacity
        )
        self.hotkey_opacity_up = keyboard.HotKey(
            keyboard.HotKey.parse(shortcuts.get('hotkey_opacity_up', '<ctrl>+<shift>+]')),
            self.increase_opacity
        )
        self.hotkey_snip = keyboard.HotKey(
            keyboard.HotKey.parse(shortcuts.get('hotkey_snip', '<shift>+a+s')),
            self.on_activate_snip
        )

        # Load the 4-times Ctrl hotkey settings
        self.ask_dialog_key = shortcuts.get('hotkey_ask_dialog_key', 'ctrl').lower()
        self.ask_dialog_press_count = int(shortcuts.get('hotkey_ask_dialog_count', '4'))
        self.ask_dialog_time_window = float(shortcuts.get('hotkey_ask_dialog_time_window', '1.0'))

    def start(self):
        self.listener = keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release)
        self.listener.start()

    def on_press(self, key):
        self.hotkey_topmost_on.press(self.listener.canonical(key))
        self.hotkey_topmost_off.press(self.listener.canonical(key))
        self.hotkey_opacity_down.press(self.listener.canonical(key))
        self.hotkey_opacity_up.press(self.listener.canonical(key))
        self.hotkey_snip.press(self.listener.canonical(key))

        # Handle Ctrl key presses
        if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
            pass  # Do nothing on press
        else:
            # Any other key resets the count
            self.ctrl_press_count = 0

    def on_release(self, key):
        self.hotkey_topmost_on.release(self.listener.canonical(key))
        self.hotkey_topmost_off.release(self.listener.canonical(key))
        self.hotkey_opacity_down.release(self.listener.canonical(key))
        self.hotkey_opacity_up.release(self.listener.canonical(key))
        self.hotkey_snip.release(self.listener.canonical(key))

        # Handle Ctrl key releases
        if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
            current_time = time.time()
            if current_time - self.ctrl_last_release_time > self.ask_dialog_time_window:
                # Too much time has passed; reset counter
                self.ctrl_press_count = 0
            self.ctrl_press_count += 1
            self.ctrl_last_release_time = current_time

            if self.ctrl_press_count >= self.ask_dialog_press_count:
                # Check if all releases are within the time window
                if current_time - (self.ctrl_last_release_time - self.ask_dialog_time_window) <= self.ask_dialog_time_window:
                    # Reset counter
                    self.ctrl_press_count = 0
                    # Open AskDialog
                    self.root.after(0, self.app.open_global_ask_dialog)
        else:
            # Any other key resets the count
            self.ctrl_press_count = 0

    def toggle_topmost_on(self):
        toggle_always_on_top()

    def toggle_topmost_off(self):
        toggle_always_on_top()

    def decrease_opacity(self):
        hwnd = get_foreground_window()
        if hwnd:
            current_opacity = get_window_opacity(hwnd)
            new_opacity = max(0.1, current_opacity - 0.1)
            set_window_opacity(hwnd, new_opacity)
            print(f"Window opacity decreased to {new_opacity * 100:.0f}%")

    def increase_opacity(self):
        hwnd = get_foreground_window()
        if hwnd:
            current_opacity = get_window_opacity(hwnd)
            new_opacity = min(1.0, current_opacity + 0.1)
            set_window_opacity(hwnd, new_opacity)
            print(f"Window opacity increased to {new_opacity * 100:.0f}%")

    def on_activate_snip(self):
        print("Snipping hotkey activated")
        self.root.after(0, lambda: self.root.snipping_tool.start_snipping())

# 从配置文件加载热键
def load_config():
    config = {
        'hotkey_topmost_on': '<cmd>+<shift>+/',
        'hotkey_topmost_off': '<cmd>+<shift>+\\',
        'hotkey_opacity_down': '<cmd>+<shift>+[',
        'hotkey_opacity_up': '<cmd>+<shift>+]'
    }
    return config