import keyboard
import threading
import time
from typing import Optional

class HotkeyCapture:
    def __init__(self):
        self.keys = set()
        self.is_capturing = False
        self.capture_thread = None
    
    def start_capture(self):
        """开始捕获按键"""
        self.keys.clear()
        self.is_capturing = True
        
        def on_press(event):
            if self.is_capturing:
                self.keys.add(event.name)
        
        def on_release(event):
            if self.is_capturing:
                if event.name in self.keys:
                    self.keys.remove(event.name)
        
        keyboard.on_press(on_press)
        keyboard.on_release(on_release)
    
    def stop_capture(self):
        """停止捕获按键"""
        self.is_capturing = False
        keyboard.unhook_all()
    
    def capture(self, timeout: float = 2.0) -> Optional[str]:
        """捕获快捷键组合"""
        self.start_capture()
        time.sleep(timeout)
        self.stop_capture()
        
        if self.keys:
            return '+'.join(sorted(self.keys))
        return None 