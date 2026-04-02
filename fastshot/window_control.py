# window_control.py

import os
import sys
import time
import math
from pynput import keyboard, mouse

# Platform-aware imports
_IS_WINDOWS = os.name == 'nt'

if _IS_WINDOWS:
    try:
        import ctypes
        from ctypes import wintypes
        import win32gui
        import win32con
        import win32process
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
    except ImportError:
        _IS_WINDOWS = False
        print("WARNING: win32 modules not available on this system")

# Import platform abstraction
from fastshot.app_platform import window_control as _platform_wc

# Constants (Windows-specific, but kept for backward compat)
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
    """Get the foreground window handle — cross-platform."""
    if _IS_WINDOWS:
        hwnd = user32.GetForegroundWindow()
        if hwnd and user32.IsWindow(hwnd) and user32.IsWindowVisible(hwnd):
            try:
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
                    return hwnd  # Return hwnd even if we can't get process details
            except Exception as e:
                print(f"Error getting foreground window info: {e}")
                return hwnd
        else:
            print("Cannot get valid foreground window handle or window is not visible")
            return None
    else:
        # macOS/Linux: return platform info dict
        return _platform_wc().get_foreground_window()


def open_process(pid):
    """Windows-only: open a process handle."""
    if not _IS_WINDOWS:
        return None
    PROCESS_ALL_ACCESS = (0x000F0000 | 0x00100000 | 0xFFF)
    return kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)


def set_window_opacity(hwnd, opacity):
    """Set window opacity — cross-platform."""
    global current_window_opacity
    opacity = max(0.1, min(opacity, 1.0))
    current_window_opacity = opacity
    print(f"Setting opacity: {opacity * 100}%")

    if _IS_WINDOWS and isinstance(hwnd, int):
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)
        user32.SetLayeredWindowAttributes(hwnd, 0, int(255 * opacity), LWA_ALPHA)
    else:
        # For macOS, hwnd would be a tkinter window or platform handle
        _platform_wc().set_window_opacity(hwnd, opacity)


def get_window_opacity(hwnd):
    global current_window_opacity
    return current_window_opacity


def toggle_always_on_top():
    """Toggle always-on-top for the foreground window."""
    if _IS_WINDOWS:
        hwnd = get_foreground_window()
        if hwnd == 0 or hwnd is None:
            return
        window_title = win32gui.GetWindowText(hwnd)
        try:
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            is_topmost = bool(ex_style & win32con.WS_EX_TOPMOST)
            if is_topmost:
                win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                                      win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
                print(f"Window '{window_title}' is no longer always on top.")
            else:
                win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                                      win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
                print(f"Window '{window_title}' is now always on top.")
        except Exception as e:
            print(f"Exception while toggling always-on-top: {e}")
    else:
        # macOS: toggling topmost on external windows is limited
        print("Toggle always-on-top: limited to Fastshot windows on macOS")


def resize_foreground_window(zoom_in):
    """Resizes the foreground window, keeping it centered."""
    if _IS_WINDOWS:
        hwnd = get_foreground_window()
        if not hwnd:
            return
        try:
            rect = wintypes.RECT()
            if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return
            current_x = rect.left
            current_y = rect.top
            current_width = rect.right - rect.left
            current_height = rect.bottom - rect.top
            if current_width <= 0 or current_height <= 0:
                return
            zoom_factor = 1.1 if zoom_in else 1 / 1.1
            new_width = int(math.ceil(current_width * zoom_factor))
            new_height = int(math.ceil(current_height * zoom_factor))
            min_size = 50
            if new_width < min_size or new_height < min_size:
                return
            delta_width = new_width - current_width
            delta_height = new_height - current_height
            new_x = current_x - delta_width // 2
            new_y = current_y - delta_height // 2
            if user32.MoveWindow(hwnd, new_x, new_y, new_width, new_height, True):
                pass
            else:
                print(f"Resize: MoveWindow failed for HWND {hwnd}.")
        except Exception as e:
            print(f"Exception during window resize: {e}")
    else:
        print("Resize foreground window: not supported on macOS for external windows")


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

        # Build VK -> unshifted char mapping for macOS canonical key normalization.
        # On macOS, pressing Shift+4 delivers '$' instead of '4'. This table lets
        # _canonical() map the VK code back to the unshifted character so HotKey
        # matching works regardless of modifier state.
        self._vk_to_char = {}
        if sys.platform == 'darwin':
            try:
                from pynput._util.darwin_vks import SYMBOLS
                for vk, ch in SYMBOLS.items():
                    if ch.isprintable():
                        self._vk_to_char[vk] = ch.lower()
            except ImportError:
                pass

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

        # On macOS, F1-F12 are media keys by default (brightness, volume, etc.)
        # Users must press fn+F-key to get standard function key behavior.
        # Use Ctrl+Shift+number as macOS-friendly defaults for Shift+F-key hotkeys.
        _is_mac = sys.platform == 'darwin'

        def _mac_default(mac_default, win_default):
            """Return macOS-friendly default if on macOS, else Windows default."""
            return mac_default if _is_mac else win_default

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
            keyboard.HotKey.parse(shortcuts.get('hotkey_toggle_visibility',
                                                _mac_default('<ctrl>+<shift>+1', '<shift>+<f1>'))),
            self.on_toggle_visibility
        )
        self.hotkey_load_image = keyboard.HotKey(
            keyboard.HotKey.parse(shortcuts.get('hotkey_load_image',
                                                _mac_default('<ctrl>+<shift>+2', '<shift>+<f2>'))),
            self.on_activate_load_image
        )
        # Add the new hotkey for repositioning image windows
        self.hotkey_reposition_windows = keyboard.HotKey(
            keyboard.HotKey.parse(shortcuts.get('hotkey_reposition_windows',
                                                _mac_default('<ctrl>+<shift>+3', '<shift>+<f3>'))),
            self.on_reposition_windows
        )
        # Add new hotkeys for session save/load
        self.hotkey_save_session = keyboard.HotKey(
            keyboard.HotKey.parse(shortcuts.get('hotkey_save_session',
                                                _mac_default('<ctrl>+<shift>+4', '<shift>+<f4>'))),
            self.on_save_session
        )
        self.hotkey_load_session = keyboard.HotKey(
            keyboard.HotKey.parse(shortcuts.get('hotkey_load_session',
                                                _mac_default('<ctrl>+<shift>+5', '<shift>+<f5>'))),
            self.on_load_session
        )
        self.hotkey_session_manager = keyboard.HotKey(
            keyboard.HotKey.parse(shortcuts.get('hotkey_session_manager',
                                                _mac_default('<ctrl>+<shift>+6', '<shift>+<f6>'))),
            self.on_session_manager
        )
        self.hotkey_quick_notes = keyboard.HotKey(
            keyboard.HotKey.parse(shortcuts.get('hotkey_quick_notes',
                                                _mac_default('<ctrl>+<shift>+7', '<shift>+<f7>'))),
            self.on_quick_notes
        )
        self.hotkey_image_gallery = keyboard.HotKey(
            keyboard.HotKey.parse(shortcuts.get('hotkey_image_gallery',
                                                _mac_default('<ctrl>+<shift>+8', '<shift>+<f8>'))),
            self.on_image_gallery
        )
        self.hotkey_recover_cache = keyboard.HotKey(
            keyboard.HotKey.parse(shortcuts.get('hotkey_recover_cache',
                                                _mac_default('<ctrl>+<shift>+0', '<shift>+<f12>'))),
            self.on_recover_cache
        )

        # Load the 4-times Ctrl hotkey settings
        self.ask_dialog_key = shortcuts.get('hotkey_ask_dialog_key', 'ctrl').lower()
        self.ask_dialog_press_count = int(shortcuts.get('hotkey_ask_dialog_count', '4'))
        self.ask_dialog_time_window = float(shortcuts.get('hotkey_ask_dialog_time_window', '1.0'))

    def start(self):
        print("Starting HotkeyListener (Keyboard & Mouse)")

        # Debug: dump all registered hotkeys on non-Windows
        if os.name != 'nt':
            print("[HOTKEY DEBUG] Registered hotkeys:")
            for name in sorted(attr for attr in dir(self) if attr.startswith('hotkey_')):
                hk = getattr(self, name, None)
                if hk and hasattr(hk, '_keys'):
                    print(f"  {name}: _keys={hk._keys}")

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
            elif key == keyboard.Key.cmd or key == keyboard.Key.cmd_l or key == keyboard.Key.cmd_r:
                return 'cmd'
            # Add other special keys as needed
            else:
                return str(key).lower().replace('key.', '')
        else:
            try:
                return key.char.lower()
            except AttributeError:
                return str(key).lower().replace('key.', '')

    def _canonical(self, key):
        """Safe canonical: avoids calling TIS APIs on background thread (macOS crash).

        On macOS, pynput's listener.canonical() calls TIS APIs that must run on
        the main thread. This replacement uses VK-based lookup (via the SYMBOLS
        table from pynput) to map shifted characters back to their unshifted form
        (e.g., '$' -> '4' when vk=21) so that HotKey matching works correctly
        even when modifier keys change the delivered character.
        """
        from pynput.keyboard import Key, KeyCode, _NORMAL_MODIFIERS
        if isinstance(key, KeyCode):
            if key.vk is not None and key.vk in self._vk_to_char:
                # Use VK-based lookup to get the unshifted character
                # This handles cases where Shift changes '4' to '$', etc.
                return KeyCode.from_char(self._vk_to_char[key.vk])
            elif key.char is not None and key.char.isprintable():
                return KeyCode.from_char(key.char.lower())
            elif key.vk is not None:
                return KeyCode.from_vk(key.vk)
            return key
        elif isinstance(key, Key) and key.value in _NORMAL_MODIFIERS:
            return _NORMAL_MODIFIERS[key.value]
        elif isinstance(key, Key) and hasattr(key.value, 'vk') and key.value.vk is not None:
            return KeyCode.from_vk(key.value.vk)
        else:
            return key

    def on_press(self, key):
        if key in self.modifiers:
            self.modifiers[key] = True

        ck = self._canonical(key)
        if os.name != 'nt':
            # Debug log for macOS hotkey diagnosis
            raw_name = key.name if isinstance(key, keyboard.Key) else repr(key)
            ck_name = ck.name if isinstance(ck, keyboard.Key) else repr(ck)
            vk = None
            if isinstance(key, keyboard.Key) and hasattr(key.value, 'vk'):
                vk = key.value.vk
            elif hasattr(key, 'vk') and key.vk is not None:
                vk = key.vk
            print(f"[HOTKEY] PRESS raw={raw_name} canonical={ck_name} vk={vk}")

        self.hotkey_topmost_on.press(ck)
        self.hotkey_topmost_off.press(ck)
        self.hotkey_opacity_down.press(ck)
        self.hotkey_opacity_up.press(ck)
        self.hotkey_snip.press(ck)
        self.hotkey_toggle_visibility.press(ck)
        self.hotkey_load_image.press(ck)
        self.hotkey_reposition_windows.press(ck)
        self.hotkey_save_session.press(ck)
        self.hotkey_load_session.press(ck)
        self.hotkey_session_manager.press(ck)
        self.hotkey_quick_notes.press(ck)
        self.hotkey_image_gallery.press(ck)
        self.hotkey_recover_cache.press(ck)

        if key not in [keyboard.Key.ctrl_l, keyboard.Key.ctrl_r]:
            if self.ctrl_press_count < self.ask_dialog_press_count:
                self.ctrl_press_count = 0

    def on_release(self, key):
        if key in self.modifiers:
            self.modifiers[key] = False

        ck = self._canonical(key)
        self.hotkey_topmost_on.release(ck)
        self.hotkey_topmost_off.release(ck)
        self.hotkey_opacity_down.release(ck)
        self.hotkey_opacity_up.release(ck)
        self.hotkey_snip.release(ck)
        self.hotkey_toggle_visibility.release(ck)
        self.hotkey_load_image.release(ck)
        self.hotkey_reposition_windows.release(ck)
        self.hotkey_save_session.release(ck)
        self.hotkey_load_session.release(ck)
        self.hotkey_session_manager.release(ck)
        self.hotkey_quick_notes.release(ck)
        self.hotkey_image_gallery.release(ck)
        self.hotkey_recover_cache.release(ck)

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

    def _get_image_window_at_cursor(self):
        """Find the Fastshot ImageWindow under the mouse cursor (macOS)."""
        if not hasattr(self.app, 'image_windows'):
            return None
        try:
            mx = self.root.winfo_pointerx()
            my = self.root.winfo_pointery()
        except Exception:
            return None
        for iw in self.app.image_windows:
            try:
                w = iw.img_window
                x, y = w.winfo_rootx(), w.winfo_rooty()
                width, height = w.winfo_width(), w.winfo_height()
                if x <= mx <= x + width and y <= my <= y + height:
                    return iw
            except Exception:
                continue
        return None

    def toggle_topmost_on(self):
        if _IS_WINDOWS:
            toggle_always_on_top()
        else:
            self.root.after(0, self._toggle_topmost_mac)

    def toggle_topmost_off(self):
        if _IS_WINDOWS:
            toggle_always_on_top()
        else:
            self.root.after(0, self._toggle_topmost_mac)

    def _toggle_topmost_mac(self):
        """Toggle always-on-top for the Fastshot window under the cursor (macOS)."""
        iw = self._get_image_window_at_cursor()
        if iw:
            w = iw.img_window
            current = w.attributes('-topmost')
            new_val = not bool(current)
            w.attributes('-topmost', new_val)
            print(f"Window topmost {'ON' if new_val else 'OFF'}")
        else:
            print("No Fastshot window under cursor")

    def decrease_opacity(self):
        if _IS_WINDOWS:
            hwnd = get_foreground_window()
            if hwnd:
                current_opacity = get_window_opacity(hwnd)
                if current_opacity > 0.1:
                    new_opacity = current_opacity - 0.1
                else:
                    new_opacity = 1.0  # Reset to 100% opacity
                new_opacity = round(new_opacity, 1)
                set_window_opacity(hwnd, new_opacity)
                print(f"Window opacity decreased to {new_opacity * 100:.0f}%")
        else:
            self.root.after(0, lambda: self._adjust_opacity_mac(-0.1))

    def increase_opacity(self):
        if _IS_WINDOWS:
            hwnd = get_foreground_window()
            if hwnd:
                current_opacity = get_window_opacity(hwnd)
                if current_opacity < 1.0:
                    new_opacity = current_opacity + 0.1
                else:
                    new_opacity = 0.1  # Reset to 10% opacity
                new_opacity = round(new_opacity, 1)
                set_window_opacity(hwnd, new_opacity)
                print(f"Window opacity increased to {new_opacity * 100:.0f}%")
        else:
            self.root.after(0, lambda: self._adjust_opacity_mac(0.1))

    def _adjust_opacity_mac(self, delta):
        """Adjust opacity of the Fastshot window under the cursor (macOS)."""
        iw = self._get_image_window_at_cursor()
        if iw:
            w = iw.img_window
            current = float(w.attributes('-alpha'))
            new_opacity = current + delta
            if new_opacity > 1.0:
                new_opacity = 0.1
            elif new_opacity < 0.1:
                new_opacity = 1.0
            new_opacity = round(new_opacity, 1)
            w.attributes('-alpha', new_opacity)
            print(f"Window opacity set to {new_opacity * 100:.0f}%")
        else:
            print("No Fastshot window under cursor")

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
            if hasattr(self.app, 'open_session_manager'):
                self.root.after(0, self.app.open_session_manager)
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

    def on_image_gallery(self):
        """Callback for the image gallery hotkey."""
        print("Image gallery hotkey activated")
        try:
            if hasattr(self.app, 'open_image_gallery'):
                self.root.after(0, self.app.open_image_gallery)
            else:
                print("ERROR: app does not have open_image_gallery method")
        except Exception as e:
            print(f"ERROR in on_image_gallery: {e}")
            import traceback
            traceback.print_exc()

    def on_recover_cache(self):
        """Callback for the recover from temp cache hotkey."""
        print("Recover cache hotkey activated (Shift+F12)")
        try:
            if hasattr(self.app, 'recover_from_cache'):
                self.root.after(0, self.app.recover_from_cache)
            else:
                print("ERROR: app does not have recover_from_cache method")
        except Exception as e:
            print(f"ERROR in on_recover_cache: {e}")
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
