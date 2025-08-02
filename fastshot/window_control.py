# window_control.py

import ctypes
from ctypes import wintypes
from pynput import keyboard, mouse
import win32gui
import win32con
import win32process
import time
import math

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Constants
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x80000
LWA_ALPHA = 0x2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_SHOWWINDOW = 0x0040

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

def resize_foreground_window(zoom_in):
    """Resizes the foreground window, keeping it centered."""
    hwnd = get_foreground_window()
    if not hwnd:
        print("Resize: No valid foreground window found.")
        return

    try:
        # Get current window position and size
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            print(f"Resize: Failed to get window rect for HWND {hwnd}")
            return

        current_x = rect.left
        current_y = rect.top
        current_width = rect.right - rect.left
        current_height = rect.bottom - rect.top

        if current_width <= 0 or current_height <= 0:
             print(f"Resize: Invalid window dimensions ({current_width}x{current_height}).")
             return

        # Define zoom factor
        zoom_factor = 1.1 if zoom_in else 1 / 1.1

        # Calculate new dimensions
        new_width = int(math.ceil(current_width * zoom_factor))
        new_height = int(math.ceil(current_height * zoom_factor))

        # Prevent window from becoming too small
        min_size = 50 # Minimum width/height in pixels
        if new_width < min_size or new_height < min_size:
            print(f"Resize: Minimum size ({min_size}px) reached.")
            return

        # Calculate position adjustment to keep window centered
        delta_width = new_width - current_width
        delta_height = new_height - current_height
        new_x = current_x - delta_width // 2
        new_y = current_y - delta_height // 2

        # Use MoveWindow to resize and reposition
        # BOOL MoveWindow(HWND hWnd, int X, int Y, int nWidth, int nHeight, BOOL bRepaint);
        if user32.MoveWindow(hwnd, new_x, new_y, new_width, new_height, True):
             # print(f"Resized window {hwnd} to {new_width}x{new_height} at ({new_x},{new_y})")
             pass
        else:
             print(f"Resize: MoveWindow failed for HWND {hwnd}. Error: {kernel32.GetLastError()}")

    except Exception as e:
        print(f"Exception during window resize: {e}")

class HotkeyListener:
    def __init__(self, config, root, app):
        self.plugin_shortcuts = {}
        self.plugin_key_counts = {}
        self.plugin_last_press_times = {}
        
        # Alternate hotkey tracking
        self.alternate_hotkey_sequences = {}  # plugin_id -> sequence state
        self.alternate_hotkey_configs = {}    # plugin_id -> config
        
        self.config = config
        self.root = root  # Tkinter root window
        self.app = app  # Reference to main application
        self.load_hotkeys()
        self.listener = None
        self.mouse_listener = None
        self.ctrl_press_count = 0
        self.ctrl_last_release_time = 0.0
        self.modifiers = {
            keyboard.Key.ctrl_l: False, keyboard.Key.ctrl_r: False,
            keyboard.Key.shift_l: False, keyboard.Key.shift_r: False,
        }

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
        # Check if this is an alternate hotkey pattern
        if key_str in ['ctrl_alt_alternate', 'ctrl_win_alternate']:
            self.register_alternate_hotkey(plugin_id, key_str, press_times)
        else:
            self.plugin_shortcuts[key_str] = {
                'plugin_id': plugin_id,
                'press_times': press_times
            }
            self.plugin_key_counts[key_str] = 0
            self.plugin_last_press_times[key_str] = 0
    
    def register_alternate_hotkey(self, plugin_id, pattern, press_times):
        """Register an alternate hotkey pattern."""
        if pattern == 'ctrl_alt_alternate':
            keys = ['ctrl', 'alt'] * (press_times // 2)
        elif pattern == 'ctrl_win_alternate':
            keys = ['ctrl', 'cmd'] * (press_times // 2)
        else:
            return
        
        self.alternate_hotkey_configs[plugin_id] = {
            'pattern': pattern,
            'keys': keys,
            'total_presses': press_times
        }
        
        self.alternate_hotkey_sequences[plugin_id] = {
            'current_step': 0,
            'last_press_time': 0,
            'timeout': 2.0  # 2 seconds timeout for the sequence
        }

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
        self.hotkey_toggle_visibility = keyboard.HotKey(
            keyboard.HotKey.parse(shortcuts.get('hotkey_toggle_visibility', '<shift>+<f1>')),
            self.on_toggle_visibility
        )
        self.hotkey_load_image = keyboard.HotKey(
            keyboard.HotKey.parse(shortcuts.get('hotkey_load_image', '<shift>+<f2>')),
            self.on_activate_load_image
        )
        # Add the new hotkey for repositioning image windows
        self.hotkey_reposition_windows = keyboard.HotKey(
            keyboard.HotKey.parse(shortcuts.get('hotkey_reposition_windows', '<shift>+<f3>')),
            self.on_reposition_windows
        )
        # Add new hotkeys for session save/load
        self.hotkey_save_session = keyboard.HotKey(
            keyboard.HotKey.parse(shortcuts.get('hotkey_save_session', '<shift>+<f4>')),
            self.on_save_session
        )
        self.hotkey_load_session = keyboard.HotKey(
            keyboard.HotKey.parse(shortcuts.get('hotkey_load_session', '<shift>+<f5>')),
            self.on_load_session
        )
        self.hotkey_session_manager = keyboard.HotKey(
            keyboard.HotKey.parse(shortcuts.get('hotkey_session_manager', '<shift>+<f6>')),
            self.on_session_manager
        )
        self.hotkey_quick_notes = keyboard.HotKey(
            keyboard.HotKey.parse(shortcuts.get('hotkey_quick_notes', '<shift>+<f7>')),
            self.on_quick_notes
        )

        # Load the 4-times Ctrl hotkey settings
        self.ask_dialog_key = shortcuts.get('hotkey_ask_dialog_key', 'ctrl').lower()
        self.ask_dialog_press_count = int(shortcuts.get('hotkey_ask_dialog_count', '4'))
        self.ask_dialog_time_window = float(shortcuts.get('hotkey_ask_dialog_time_window', '1.0'))

    def start(self):
        print("Starting HotkeyListener (Keyboard & Mouse)")
        self.listener = keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release)
        self.register_plugin_hotkeys()
        self.listener.start()

        self.mouse_listener = mouse.Listener(
            on_scroll=self.on_scroll
        )
        self.mouse_listener.start()

    def stop(self):
        """Stops both keyboard and mouse listeners."""
        if self.listener:
            self.listener.stop()
            self.listener = None
            print("Stopped Keyboard Listener")
        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None
            print("Stopped Mouse Listener")

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
        if key in self.modifiers:
            self.modifiers[key] = True

        self.hotkey_topmost_on.press(self.listener.canonical(key))
        self.hotkey_topmost_off.press(self.listener.canonical(key))
        self.hotkey_opacity_down.press(self.listener.canonical(key))
        self.hotkey_opacity_up.press(self.listener.canonical(key))
        self.hotkey_snip.press(self.listener.canonical(key))
        self.hotkey_toggle_visibility.press(self.listener.canonical(key))
        self.hotkey_load_image.press(self.listener.canonical(key))
        self.hotkey_reposition_windows.press(self.listener.canonical(key))
        self.hotkey_save_session.press(self.listener.canonical(key))
        self.hotkey_load_session.press(self.listener.canonical(key))
        self.hotkey_session_manager.press(self.listener.canonical(key))
        self.hotkey_quick_notes.press(self.listener.canonical(key))

        if key not in [keyboard.Key.ctrl_l, keyboard.Key.ctrl_r]:
            if self.ctrl_press_count < self.ask_dialog_press_count:
                self.ctrl_press_count = 0

    def on_release(self, key):
        if key in self.modifiers:
            self.modifiers[key] = False

        self.hotkey_topmost_on.release(self.listener.canonical(key))
        self.hotkey_topmost_off.release(self.listener.canonical(key))
        self.hotkey_opacity_down.release(self.listener.canonical(key))
        self.hotkey_opacity_up.release(self.listener.canonical(key))
        self.hotkey_snip.release(self.listener.canonical(key))
        self.hotkey_toggle_visibility.release(self.listener.canonical(key))
        self.hotkey_load_image.release(self.listener.canonical(key))
        self.hotkey_reposition_windows.release(self.listener.canonical(key))
        self.hotkey_save_session.release(self.listener.canonical(key))
        self.hotkey_load_session.release(self.listener.canonical(key))
        self.hotkey_session_manager.release(self.listener.canonical(key))
        self.hotkey_quick_notes.release(self.listener.canonical(key))

        if key in [keyboard.Key.ctrl_l, keyboard.Key.ctrl_r]:
            current_time = time.time()
            if current_time - self.ctrl_last_release_time > self.ask_dialog_time_window:
                self.ctrl_press_count = 0
            self.ctrl_press_count += 1
            self.ctrl_last_release_time = current_time

            if self.ctrl_press_count >= self.ask_dialog_press_count:
                if current_time - (self.ctrl_last_release_time - self.ask_dialog_time_window) <= self.ask_dialog_time_window:
                    self.ctrl_press_count = 0
                    self.root.after(0, self.app.open_global_ask_dialog)
        else:
            self.ctrl_press_count = 0

        key_char = self.get_key_char(key)
        
        # Handle alternate hotkey sequences
        self.handle_alternate_hotkey(key_char)
        
        # Handle regular plugin shortcuts
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

    def on_scroll(self, x, y, dx, dy):
        ctrl_pressed = self.modifiers[keyboard.Key.ctrl_l] or self.modifiers[keyboard.Key.ctrl_r]
        shift_pressed = self.modifiers[keyboard.Key.shift_l] or self.modifiers[keyboard.Key.shift_r]

        if ctrl_pressed and shift_pressed:
            if dy != 0:
                zoom_in = dy > 0
                resize_foreground_window(zoom_in)

    def handle_alternate_hotkey(self, key_char):
        """Handle alternate hotkey sequences."""
        current_time = time.time()
        
        for plugin_id, config in self.alternate_hotkey_configs.items():
            sequence = self.alternate_hotkey_sequences[plugin_id]
            
            # Check if sequence has timed out
            if current_time - sequence['last_press_time'] > sequence['timeout']:
                sequence['current_step'] = 0
            
            # Check if this key matches the expected key in the sequence
            expected_key = config['keys'][sequence['current_step']]
            if key_char == expected_key:
                sequence['current_step'] += 1
                sequence['last_press_time'] = current_time
                
                print(f"Alternate hotkey progress for {plugin_id}: {sequence['current_step']}/{len(config['keys'])}")
                
                # Check if sequence is complete
                if sequence['current_step'] >= len(config['keys']):
                    print(f"Alternate hotkey sequence completed for {plugin_id}")
                    self.activate_plugin(plugin_id)
                    sequence['current_step'] = 0  # Reset sequence
            else:
                # Wrong key pressed, reset sequence if it was in progress
                if sequence['current_step'] > 0:
                    print(f"Alternate hotkey sequence reset for {plugin_id} (expected {expected_key}, got {key_char})")
                    sequence['current_step'] = 0

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

    def on_toggle_visibility(self):
        print("Toggle visibility hotkey activated")
        self.root.after(0, self.app.toggle_all_image_windows_visibility)

    def on_activate_load_image(self):
        print("Load image hotkey activated")
        self.root.after(0, self.app.load_image_from_dialog)

    def on_reposition_windows(self):
        """Callback for the reposition windows hotkey."""
        print("Reposition windows hotkey activated")
        self.root.after(0, self.app.reposition_all_image_windows)

    def on_save_session(self):
        """Callback for the save session hotkey."""
        print("Save session hotkey activated")
        self.root.after(0, self.app.save_session_dialog)

    def on_load_session(self):
        """Callback for the load session hotkey."""
        print("Load session hotkey activated")
        self.root.after(0, self.app.load_session_dialog)

    def on_session_manager(self):
        """Callback for the session manager hotkey."""
        print("Session manager hotkey activated")
        try:
            print(f"DEBUG: self.root = {self.root}")
            print(f"DEBUG: self.app = {self.app}")
            print(f"DEBUG: hasattr(self.app, 'open_session_manager') = {hasattr(self.app, 'open_session_manager')}")
            
            if hasattr(self.app, 'open_session_manager'):
                print("DEBUG: Calling self.root.after to schedule open_session_manager")
                self.root.after(0, self.app.open_session_manager)
                print("DEBUG: self.root.after call completed")
            else:
                print("ERROR: app does not have open_session_manager method")
        except Exception as e:
            print(f"ERROR in on_session_manager: {e}")
            import traceback
            traceback.print_exc()

    def on_quick_notes(self):
        """Callback for the quick notes hotkey."""
        print("Quick notes hotkey activated")
        try:
            if hasattr(self.app, 'open_quick_notes'):
                self.root.after(0, self.app.open_quick_notes)
            else:
                print("ERROR: app does not have open_quick_notes method")
        except Exception as e:
            print(f"ERROR in on_quick_notes: {e}")
            import traceback
            traceback.print_exc()

# 从配置文件加载热键
def load_config():
    config = {
        'hotkey_topmost_on': '<cmd>+<shift>+/',
        'hotkey_topmost_off': '<cmd>+<shift>+\\',
        'hotkey_opacity_down': '<cmd>+<shift>+[',
        'hotkey_opacity_up': '<cmd>+<shift>+]'
    }
    return config