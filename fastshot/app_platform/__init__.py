# fastshot/platform/__init__.py
"""
Platform abstraction layer for Fastshot.
Automatically detects the current OS and exports the correct implementation.
"""

import sys
import os

_platform = sys.platform  # 'win32', 'darwin', 'linux'


def get_platform_name():
    """Returns 'windows', 'macos', or 'linux'."""
    if _platform == 'win32':
        return 'windows'
    elif _platform == 'darwin':
        return 'macos'
    else:
        return 'linux'


def get_clipboard():
    """Returns a PlatformClipboard instance for the current OS."""
    name = get_platform_name()
    if name == 'windows':
        from fastshot.app_platform.windows import WindowsClipboard
        return WindowsClipboard()
    elif name == 'macos':
        from fastshot.app_platform.macos import MacOSClipboard
        return MacOSClipboard()
    else:
        raise NotImplementedError(f"Clipboard not implemented for {name}")


def get_window_control():
    """Returns a PlatformWindowControl instance for the current OS."""
    name = get_platform_name()
    if name == 'windows':
        from fastshot.app_platform.windows import WindowsWindowControl
        return WindowsWindowControl()
    elif name == 'macos':
        from fastshot.app_platform.macos import MacOSWindowControl
        return MacOSWindowControl()
    else:
        raise NotImplementedError(f"Window control not implemented for {name}")


# Convenience: pre-instantiate singletons
_clipboard = None
_window_control = None


def clipboard():
    """Get the singleton clipboard instance."""
    global _clipboard
    if _clipboard is None:
        _clipboard = get_clipboard()
    return _clipboard


def window_control():
    """Get the singleton window control instance."""
    global _window_control
    if _window_control is None:
        _window_control = get_window_control()
    return _window_control


# Monitor detection - use platform-specific implementation
def get_monitors():
    """Get list of monitors using platform-specific implementation."""
    from fastshot.app_platform.base import get_monitors as _get_monitors
    return _get_monitors()
