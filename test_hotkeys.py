#!/usr/bin/env python3
"""
Test script to diagnose Shift+Fx hotkey issues on macOS.
Run this script and press Shift+F4, Shift+F12, etc. to see what pynput receives.

Usage: .venv/bin/python test_hotkeys.py
Press Ctrl+C or q to quit.
"""

import sys
import os

# Ensure we use the project's venv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pynput import keyboard
from pynput.keyboard import Key, KeyCode, _NORMAL_MODIFIERS

# Monkey-patch keycode_context BEFORE starting listener
def _patch_keycode_context():
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
        print("Patched pynput keycode_context for macOS 26.x compatibility")
    except Exception as e:
        print(f"keycode_context patch skipped: {e}")

_patch_keycode_context()


def _canonical(key):
    """Thread-safe canonical key representation."""
    if isinstance(key, KeyCode):
        if key.char is not None and key.char.isprintable():
            return KeyCode.from_char(key.char.lower())
        elif key.vk is not None:
            return KeyCode.from_vk(key.vk)
        return key
    elif isinstance(key, Key) and key.value in _NORMAL_MODIFIERS:
        return _NORMAL_MODIFIERS[key.value]
    elif isinstance(key, Key) and key.value.vk is not None:
        return KeyCode.from_vk(key.value.vk)
    else:
        return key


# Parse hotkeys from config
hotkey_configs = {
    'toggle_visibility': '<shift>+<f1>',
    'load_image': '<shift>+<f2>',
    'reposition_windows': '<shift>+<f3>',
    'save_session': '<shift>+<f4>',
    'load_session': '<shift>+<f5>',
    'session_manager': '<shift>+<f6>',
    'quick_notes': '<shift>+<f7>',
    'image_gallery': '<shift>+<f8>',
    'recover_cache': '<shift>+<f12>',
}

# Create HotKey objects and track their state
hotkeys = {}
for name, key_str in hotkey_configs.items():
    parsed = keyboard.HotKey.parse(key_str)
    hk = keyboard.HotKey(parsed, lambda n=name: print(f"  *** HOTKEY TRIGGERED: {n} ***"))
    hotkeys[name] = (hk, parsed)
    print(f"Registered: {name} = {key_str} -> parsed keys: {parsed}")


def on_press(key):
    ck = _canonical(key)
    raw_repr = f"Key.{key.name}" if isinstance(key, Key) else repr(key)
    canon_repr = f"Key.{ck.name}" if isinstance(ck, Key) else repr(ck)

    # Get VK if available
    vk = None
    if isinstance(key, Key) and hasattr(key.value, 'vk'):
        vk = key.value.vk
    elif isinstance(key, KeyCode) and key.vk is not None:
        vk = key.vk

    print(f"PRESS: raw={raw_repr}, canonical={canon_repr}, vk=0x{vk:02X}" if vk else f"PRESS: raw={raw_repr}, canonical={canon_repr}")

    # Feed to all hotkeys
    for name, (hk, _) in hotkeys.items():
        hk.press(ck)


def on_release(key):
    ck = _canonical(key)
    raw_repr = f"Key.{key.name}" if isinstance(key, Key) else repr(key)
    canon_repr = f"Key.{ck.name}" if isinstance(ck, Key) else repr(ck)

    print(f"RELEASE: raw={raw_repr}, canonical={canon_repr}")

    # Feed to all hotkeys
    for name, (hk, _) in hotkeys.items():
        hk.release(ck)

    # Quit on 'q'
    if isinstance(key, KeyCode) and key.char == 'q':
        print("Quitting...")
        listener.stop()
        return False


print("\n=== Press Shift+F1..F12 to test hotkeys. Press 'q' to quit. ===\n")

listener = keyboard.Listener(on_press=on_press, on_release=on_release)
listener.start()

try:
    listener.join()
except KeyboardInterrupt:
    listener.stop()
    print("\nStopped.")
