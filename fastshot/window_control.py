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
        self.plugin_shortcuts = {}
        self.plugin_key_counts = {}
        self.plugin_last_press_times = {}
        self.config = config
        self.root = root  # Tkinter root window
        self.app = app  # Reference to main application
        self.load_hotkeys()
        self.listener = None
        self.ctrl_press_count = 0
        self.ctrl_last_release_time = 0.0

    def register_plugin_hotkeys(self):
        for plugin_id, plugin_data in self.app.plugins.items():
            try:
                plugin_info = plugin_data['info']
                if plugin_info.get('enabled', True):
                    key_str = plugin_info.get('default_shortcut')
                    press_times = int(plugin_info.get('press_times', 1))
                    self.register_plugin_hotkey(plugin_id, key_str, press_times)
                    print(f"Registered plugin hotkey: {plugin_info['name']}, key: {key_str}, press_times: {press_times}")
            except Exception as e:
                print(f"Error registering plugin hotkey for {plugin_id}: {e}")
                continue

    def register_plugin_hotkey(self, plugin_id, key_str, press_times):
        self.plugin_shortcuts[key_str] = {
            'plugin_id': plugin_id,
            'press_times': press_times
        }
        self.plugin_key_counts[key_str] = 0
        self.plugin_last_press_times[key_str] = 0

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
        print("Starting HotkeyListener") 
        self.listener = keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release)
        self.register_plugin_hotkeys()  # Add this line
        self.listener.start()


    def get_key_char(self, key):
        if isinstance(key, keyboard.Key):
            # Handle special keys
            if key == keyboard.Key.alt or key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
                return 'alt'
            elif key == keyboard.Key.ctrl or key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                return 'ctrl'
            elif key == keyboard.Key.shift or key == keyboard.Key.shift_l or key == keyboard.Key.shift_r:
                return 'shift'
            elif key == keyboard.Key.cmd:
                return 'cmd'
            # Add other special keys as needed
            else:
                return str(key).lower().replace('key.', '')
        else:
            try:
                return key.char.lower()
            except AttributeError:
                return str(key).lower().replace('key.', '')

    def on_press(self, key):
        print(f"Key pressed: {key}")
        # Existing code...
        # ---------------------------------------
        self.hotkey_topmost_on.press(self.listener.canonical(key))
        self.hotkey_topmost_off.press(self.listener.canonical(key))
        self.hotkey_opacity_down.press(self.listener.canonical(key))
        self.hotkey_opacity_up.press(self.listener.canonical(key))
        self.hotkey_snip.press(self.listener.canonical(key))

        # Handle Ctrl key presses
        # ---------------------------------------
        if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
            pass  # Do nothing on press
        else:
            # Any other key resets the count
            self.ctrl_press_count = 0
 

    def on_release(self, key):
        print(f"Key released: {key}") 
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

        # ---------------------------------------
        # Handle plugin hotkeys
        key_char = self.get_key_char(key)
        print(f"Key pressed: {key_char}")  # Debug statement
        if key_char in self.plugin_shortcuts:
            current_time = time.time()
            last_press_time = self.plugin_last_press_times.get(key_char, 0)
            if current_time - last_press_time > 1.0:
                self.plugin_key_counts[key_char] = 1
            else:
                self.plugin_key_counts[key_char] += 1

            self.plugin_last_press_times[key_char] = current_time

            if self.plugin_key_counts[key_char] >= self.plugin_shortcuts[key_char]['press_times']:
                plugin_id = self.plugin_shortcuts[key_char]['plugin_id']
                self.activate_plugin(plugin_id)
                self.plugin_key_counts[key_char] = 0

    def activate_plugin(self, plugin_id):
        plugin_data = self.app.plugins.get(plugin_id)
        if plugin_data:
            plugin_module = plugin_data['module']
            try:
                plugin_module.run(self.app)
                print(f"Activated plugin: {plugin_data['info']['name']}")
            except Exception as e:
                print(f"Error activating plugin {plugin_id}: {e}")


    def toggle_topmost_on(self):
        toggle_always_on_top()

    def toggle_topmost_off(self):
        toggle_always_on_top()

    def decrease_opacity(self):
        hwnd = get_foreground_window()
        if hwnd:
            current_opacity = get_window_opacity(hwnd)
            if current_opacity > 0.1:
                new_opacity = current_opacity - 0.1
            else:
                new_opacity = 1.0  # Reset to 100% opacity
            new_opacity = round(new_opacity, 1)  # Ensure precision
            set_window_opacity(hwnd, new_opacity)
            print(f"Window opacity decreased to {new_opacity * 100:.0f}%")

    def increase_opacity(self):
        hwnd = get_foreground_window()
        if hwnd:
            current_opacity = get_window_opacity(hwnd)
            if current_opacity < 1.0:
                new_opacity = current_opacity + 0.1
            else:
                new_opacity = 0.1  # Reset to 10% opacity
            new_opacity = round(new_opacity, 1)  # Ensure precision
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