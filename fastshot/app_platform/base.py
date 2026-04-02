# fastshot/platform/base.py
"""
Abstract base classes for platform-specific operations.
Each platform (Windows/macOS) provides a concrete implementation.
"""

import sys
from abc import ABC, abstractmethod
from PIL import Image


class PlatformClipboard(ABC):
    """Abstract clipboard operations."""

    @abstractmethod
    def copy_image(self, image: Image.Image) -> None:
        """Copy a PIL Image to the system clipboard."""
        ...

    @abstractmethod
    def copy_text(self, text: str) -> None:
        """Copy text to the system clipboard."""
        ...

    @abstractmethod
    def get_text(self) -> str:
        """Get text from the system clipboard."""
        ...

    @abstractmethod
    def get_file_paths(self) -> list:
        """Get file paths from the system clipboard (for drag-drop / copy-paste files)."""
        ...


class PlatformWindowControl(ABC):
    """Abstract window management operations."""

    @abstractmethod
    def get_foreground_window(self):
        """Get the currently focused window handle/reference."""
        ...

    @abstractmethod
    def set_always_on_top(self, window_handle, enable: bool) -> None:
        """Set or unset always-on-top for a window."""
        ...

    @abstractmethod
    def set_window_opacity(self, window_handle, opacity: float) -> None:
        """Set window opacity (0.0 = transparent, 1.0 = opaque)."""
        ...

    @abstractmethod
    def get_window_opacity(self, window_handle) -> float:
        """Get current window opacity."""
        ...

    @abstractmethod
    def set_click_through(self, window_handle, enable: bool) -> None:
        """Enable or disable click-through (mouse events pass to windows below)."""
        ...

    @abstractmethod
    def bring_to_front(self, window_handle) -> None:
        """Bring a window to the foreground."""
        ...

    @abstractmethod
    def resize_window(self, window_handle, zoom_in: bool) -> None:
        """Resize a window, keeping it centered."""
        ...

    @abstractmethod
    def get_window_info(self, window_handle) -> dict:
        """Get window info (title, pid, position, size)."""
        ...


class MonitorInfo:
    """Simple container for monitor information."""
    def __init__(self, x: int, y: int, width: int, height: int, is_primary: bool = False):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.is_primary = is_primary

    def __repr__(self):
        primary_str = " (primary)" if self.is_primary else ""
        return f"MonitorInfo({self.width}x{self.height} at ({self.x}, {self.y}){primary_str})"


def get_monitors() -> list[MonitorInfo]:
    """Get list of monitors using platform-specific implementation."""
    import os
    if os.name == 'nt':
        from fastshot.app_platform.windows import get_monitors as _win_monitors
        return _win_monitors()
    elif sys.platform == 'darwin':
        from fastshot.app_platform.macos import get_monitors as _mac_monitors
        return _mac_monitors()
    else:
        # Fallback to screeninfo for Linux/other
        from screeninfo import get_monitors as _screeninfo_monitors
        from fastshot.app_platform.base import MonitorInfo
        monitors = []
        for m in _screeninfo_monitors():
            monitors.append(MonitorInfo(
                x=m.x, y=m.y, width=m.width, height=m.height,
                is_primary=getattr(m, 'is_primary', False)
            ))
        return monitors
