import threading
import time
import os
import sys
from typing import Optional
from pynput import keyboard

# Patch pynput keycode_context on macOS to avoid TIS crash
if sys.platform == 'darwin':
    try:
        import pynput._util.darwin as _pynput_darwin
        import contextlib
        with _pynput_darwin.keycode_context() as ctx:
            _cached = ctx
        @contextlib.contextmanager
        def _cached_keycode_context():
            yield _cached
        _pynput_darwin.keycode_context = _cached_keycode_context
        import pynput.keyboard._darwin as _kd
        _kd.keycode_context = _cached_keycode_context
    except Exception:
        pass

class HotkeyCapture:
    def __init__(self):
        self.keys = set()
        self.is_capturing = False
        self.listener = None
        self._modifier_mapping = {
            keyboard.Key.cmd: '<cmd>',
            keyboard.Key.cmd_r: '<cmd>',
            keyboard.Key.alt: '<alt>',
            keyboard.Key.alt_r: '<alt>',
            keyboard.Key.alt_gr: '<alt>',
            keyboard.Key.ctrl: '<ctrl>',
            keyboard.Key.ctrl_r: '<ctrl>',
            keyboard.Key.shift: '<shift>',
            keyboard.Key.shift_r: '<shift>',
        }
    
    def _get_key_name(self, key):
        if key in self._modifier_mapping:
            return self._modifier_mapping[key]
        if hasattr(key, 'char') and key.char:
            return key.char.lower()
        if hasattr(key, 'name'):
            return f"<{key.name}>"
        return str(key).replace("'", "")

    def start_capture(self):
        """开始捕获按键"""
        self.keys.clear()
        self.is_capturing = True
        
        def on_press(key):
            if self.is_capturing:
                key_name = self._get_key_name(key)
                if key_name:
                    self.keys.add(key_name)
        
        def on_release(key):
            if self.is_capturing:
                key_name = self._get_key_name(key)
                if key_name and key_name in self.keys:
                    self.keys.remove(key_name)

        self.listener = keyboard.Listener(
            on_press=on_press, 
            on_release=on_release
        )
        self.listener.start()
    
    def stop_capture(self):
        """停止捕获按键"""
        self.is_capturing = False
        if self.listener:
            self.listener.stop()
            self.listener = None
    
    def capture(self, timeout: float = 2.0) -> Optional[str]:
        """捕获快捷键组合"""
        self.start_capture()
        time.sleep(timeout)
        self.stop_capture()
        
        if self.keys:
            return '+'.join(sorted(list(self.keys)))
        return None