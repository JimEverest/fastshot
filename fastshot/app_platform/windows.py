# fastshot/platform/windows.py
"""
Windows-specific implementations for clipboard and window control.
Wraps the existing win32 API calls used throughout the original codebase.
"""

import os
import io
from PIL import Image

from fastshot.app_platform.base import PlatformClipboard, PlatformWindowControl, MonitorInfo

# Only import win32 modules on Windows
if os.name == 'nt':
    try:
        import win32clipboard
        import win32gui
        import win32con
        import win32process
        import ctypes
        _WIN32_AVAILABLE = True
    except ImportError:
        _WIN32_AVAILABLE = False
else:
    _WIN32_AVAILABLE = False

# Global opacity tracker
_current_window_opacity = 1.0


class WindowsClipboard(PlatformClipboard):
    """Windows clipboard via win32clipboard."""

    def copy_image(self, image: Image.Image) -> None:
        if not _WIN32_AVAILABLE:
            raise RuntimeError("win32clipboard not available")
        output = io.BytesIO()
        image.save(output, format='BMP')
        data = output.getvalue()[14:]  # Strip BMP header
        output.close()
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        win32clipboard.CloseClipboard()

    def copy_text(self, text: str) -> None:
        if not _WIN32_AVAILABLE:
            raise RuntimeError("win32clipboard not available")
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()

    def get_text(self) -> str:
        if not _WIN32_AVAILABLE:
            return ''
        try:
            win32clipboard.OpenClipboard()
            text = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            return text
        except:
            try:
                win32clipboard.CloseClipboard()
            except:
                pass
            return ''

    def get_file_paths(self) -> list:
        if not _WIN32_AVAILABLE:
            return []
        try:
            win32clipboard.OpenClipboard()
            data = win32clipboard.GetClipboardData(win32clipboard.CF_HDROP)
            win32clipboard.CloseClipboard()
            if data:
                return list(data)
            return []
        except:
            try:
                win32clipboard.CloseClipboard()
            except:
                pass
            return []


class WindowsWindowControl(PlatformWindowControl):
    """Windows window control via win32gui / ctypes."""

    def __init__(self):
        if _WIN32_AVAILABLE:
            self.user32 = ctypes.windll.user32
            self.kernel32 = ctypes.windll.kernel32

    def get_foreground_window(self):
        if not _WIN32_AVAILABLE:
            return None
        hwnd = self.user32.GetForegroundWindow()
        if hwnd and self.user32.IsWindow(hwnd) and self.user32.IsWindowVisible(hwnd):
            return hwnd
        return None

    def set_always_on_top(self, window_handle, enable: bool) -> None:
        if not _WIN32_AVAILABLE:
            return
        flag = win32con.HWND_TOPMOST if enable else win32con.HWND_NOTOPMOST
        win32gui.SetWindowPos(
            window_handle, flag, 0, 0, 0, 0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
        )

    def set_window_opacity(self, window_handle, opacity: float) -> None:
        global _current_window_opacity
        if not _WIN32_AVAILABLE or not window_handle:
            return
        opacity = max(0.1, min(opacity, 1.0))
        _current_window_opacity = opacity
        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x80000
        LWA_ALPHA = 0x2
        style = self.user32.GetWindowLongW(window_handle, GWL_EXSTYLE)
        self.user32.SetWindowLongW(window_handle, GWL_EXSTYLE, style | WS_EX_LAYERED)
        self.user32.SetLayeredWindowAttributes(window_handle, 0, int(255 * opacity), LWA_ALPHA)

    def get_window_opacity(self, window_handle) -> float:
        global _current_window_opacity
        return _current_window_opacity

    def set_click_through(self, window_handle, enable: bool) -> None:
        if not _WIN32_AVAILABLE or not window_handle:
            return
        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x80000
        WS_EX_TRANSPARENT = 0x20
        style = self.user32.GetWindowLongW(window_handle, GWL_EXSTYLE)
        if enable:
            style = style | WS_EX_LAYERED | WS_EX_TRANSPARENT
        else:
            style = (style | WS_EX_LAYERED) & ~WS_EX_TRANSPARENT
        self.user32.SetWindowLongW(window_handle, GWL_EXSTYLE, style)

    def bring_to_front(self, window_handle) -> None:
        if not _WIN32_AVAILABLE or not window_handle:
            return
        win32gui.SetForegroundWindow(window_handle)
        win32gui.BringWindowToTop(window_handle)

    def resize_window(self, window_handle, zoom_in: bool) -> None:
        if not _WIN32_AVAILABLE or not window_handle:
            return
        import math
        from ctypes import wintypes
        rect = wintypes.RECT()
        if not self.user32.GetWindowRect(window_handle, ctypes.byref(rect)):
            return
        cw = rect.right - rect.left
        ch = rect.bottom - rect.top
        if cw <= 0 or ch <= 0:
            return
        factor = 1.1 if zoom_in else 1 / 1.1
        nw = int(math.ceil(cw * factor))
        nh = int(math.ceil(ch * factor))
        if nw < 50 or nh < 50:
            return
        nx = rect.left - (nw - cw) // 2
        ny = rect.top - (nh - ch) // 2
        self.user32.MoveWindow(window_handle, nx, ny, nw, nh, True)

    def get_window_info(self, window_handle) -> dict:
        if not _WIN32_AVAILABLE or not window_handle:
            return {}
        try:
            title = win32gui.GetWindowText(window_handle)
            cls = win32gui.GetClassName(window_handle)
            _, pid = win32process.GetWindowThreadProcessId(window_handle)
            return {'title': title, 'class': cls, 'pid': pid}
        except:
            return {}


def get_monitors():
    """Get monitor information using Windows APIs."""
    monitors = []
    if not _WIN32_AVAILABLE:
        # Fallback to screeninfo
        from screeninfo import get_monitors as _screeninfo_monitors
        for m in _screeninfo_monitors():
            monitors.append(MonitorInfo(
                x=m.x, y=m.y, width=m.width, height=m.height,
                is_primary=getattr(m, 'is_primary', False)
            ))
        return monitors

    try:
        import ctypes
        from ctypes import wintypes

        # Define necessary structures and functions
        class MONITORINFOEXW(ctypes.Structure):
            _fields_ = [
                ('cbSize', wintypes.DWORD),
                ('rcMonitor', wintypes.RECT),
                ('rcWork', wintypes.RECT),
                ('dwFlags', wintypes.DWORD),
                ('szDevice', wintypes.WCHAR * 32)
            ]

        user32 = ctypes.windll.user32

        def _monitor_callback(hmonitor, hdc, lprect, dwData):
            """Callback for EnumDisplayMonitors."""
            info = MONITORINFOEXW()
            info.cbSize = ctypes.sizeof(MONITORINFOEXW)
            if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
                is_primary = bool(info.dwFlags & 1)  # MONITORINFOF_PRIMARY
                monitors.append(MonitorInfo(
                    x=info.rcMonitor.left,
                    y=info.rcMonitor.top,
                    width=info.rcMonitor.right - info.rcMonitor.left,
                    height=info.rcMonitor.bottom - info.rcMonitor.top,
                    is_primary=is_primary
                ))
            return True  # Continue enumeration

        # Enumerate all monitors
        user32.EnumDisplayMonitors(None, None, ctypes.WINFUNCTYPE(
            ctypes.c_bool,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulongptr,
            ctypes.c_long
        )(_monitor_callback), 0)

        return monitors

    except Exception as e:
        print(f"ERROR getting monitors via Win32 API: {e}")
        # Fallback to screeninfo
        from screeninfo import get_monitors as _screeninfo_monitors
        for m in _screeninfo_monitors():
            monitors.append(MonitorInfo(
                x=m.x, y=m.y, width=m.width, height=m.height,
                is_primary=getattr(m, 'is_primary', False)
            ))
        return monitors