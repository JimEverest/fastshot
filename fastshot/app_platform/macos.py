# fastshot/platform/macos.py
"""
macOS-specific implementations for clipboard and window control.
Uses pyobjc for native macOS API access.
"""

import subprocess
import io
import os
from PIL import Image

from fastshot.app_platform.base import PlatformClipboard, PlatformWindowControl, MonitorInfo

# Global opacity tracker (per-window, keyed by window id)
_opacity_registry = {}


def get_monitors():
    """Get monitor information using native NSScreen APIs.

    Returns dimensions in **points** (logical pixels) — the coordinate system
    used by tkinter on macOS. For physical pixel operations (e.g. mss screenshot),
    multiply by the backing scale factor.
    """
    monitors = []
    try:
        from AppKit import NSScreen

        screens = NSScreen.screens()
        if not screens:
            print("WARNING: No screens detected via NSScreen")
            return monitors

        primary_screen = screens[0]

        for i, screen in enumerate(screens):
            frame = screen.frame()
            scale_factor = screen.backingScaleFactor() or 1.0

            # Use point dimensions (logical) — tkinter works in points on macOS
            width = int(frame.size.width)
            height = int(frame.size.height)

            # Convert y from NSScreen bottom-left origin to tkinter top-left origin
            main_frame = screens[0].frame()
            main_height = int(main_frame.size.height)

            x = int(frame.origin.x)
            y = int(main_height - (frame.origin.y + frame.size.height))

            is_primary = (screen == primary_screen)

            monitors.append(MonitorInfo(x, y, width, height, is_primary))
            print(f"Monitor {i}: {width}x{height} at ({x}, {y}), primary={is_primary}, scale={scale_factor}")

        return monitors

    except ImportError:
        print("WARNING: pyobjc not available, falling back to screeninfo")
        from screeninfo import get_monitors as _screeninfo_monitors
        result = []
        for m in _screeninfo_monitors():
            result.append(MonitorInfo(
                x=m.x, y=m.y, width=m.width, height=m.height,
                is_primary=getattr(m, 'is_primary', False)
            ))
        return result
    except Exception as e:
        print(f"ERROR getting monitors via NSScreen: {e}")
        import traceback
        traceback.print_exc()
        return []


class MacOSClipboard(PlatformClipboard):
    """macOS clipboard via pyobjc NSPasteboard."""

    def copy_image(self, image: Image.Image) -> None:
        """Copy a PIL Image to macOS clipboard via NSPasteboard."""
        try:
            from AppKit import NSPasteboard, NSPasteboardTypeTIFF
            
            # Convert PIL Image to TIFF bytes (NSPasteboard natively supports TIFF)
            buffer = io.BytesIO()
            image.save(buffer, format='TIFF')
            tiff_data = buffer.getvalue()
            buffer.close()
            
            # Use NSPasteboard
            from Foundation import NSData
            pb = NSPasteboard.generalPasteboard()
            pb.clearContents()
            ns_data = NSData.dataWithBytes_length_(tiff_data, len(tiff_data))
            pb.setData_forType_(ns_data, NSPasteboardTypeTIFF)
            print("Image copied to macOS clipboard via NSPasteboard")
        except ImportError:
            # Fallback: save to temp file and use osascript
            print("pyobjc not available, using osascript fallback for image copy")
            temp_path = '/tmp/_fastshot_clipboard.tiff'
            image.save(temp_path, format='TIFF')
            script = f'''
            set the clipboard to (read (POSIX file "{temp_path}") as TIFF picture)
            '''
            subprocess.run(['osascript', '-e', script], capture_output=True)
            try:
                os.remove(temp_path)
            except:
                pass

    def copy_text(self, text: str) -> None:
        """Copy text to macOS clipboard."""
        try:
            from AppKit import NSPasteboard, NSPasteboardTypeString
            from Foundation import NSString
            
            pb = NSPasteboard.generalPasteboard()
            pb.clearContents()
            ns_string = NSString.stringWithString_(text)
            pb.setString_forType_(str(ns_string), NSPasteboardTypeString)
        except ImportError:
            # Fallback: subprocess pbcopy
            process = subprocess.Popen(['pbcopy'], env={'LANG': 'en_US.UTF-8'},
                                       stdin=subprocess.PIPE)
            process.communicate(text.encode('utf-8'))

    def get_text(self) -> str:
        """Get text from macOS clipboard."""
        try:
            from AppKit import NSPasteboard, NSPasteboardTypeString
            
            pb = NSPasteboard.generalPasteboard()
            text = pb.stringForType_(NSPasteboardTypeString)
            return str(text) if text else ''
        except ImportError:
            # Fallback: subprocess pbpaste
            result = subprocess.run(['pbpaste'], capture_output=True, text=True)
            return result.stdout

    def get_file_paths(self) -> list:
        """Get file paths from macOS clipboard (Finder copy)."""
        try:
            from AppKit import NSPasteboard, NSPasteboardTypeFileURL
            
            pb = NSPasteboard.generalPasteboard()
            # Try reading file URLs
            items = pb.pasteboardItems()
            paths = []
            if items:
                for item in items:
                    url_string = item.stringForType_(NSPasteboardTypeFileURL)
                    if url_string:
                        # Convert file URL to path
                        from Foundation import NSURL
                        url = NSURL.URLWithString_(url_string)
                        if url and url.isFileURL():
                            paths.append(str(url.path()))
            return paths
        except ImportError:
            # Fallback: try to parse pbpaste output as file paths
            result = subprocess.run(['pbpaste'], capture_output=True, text=True)
            text = result.stdout.strip()
            if text and os.path.exists(text):
                return [text]
            return []


class MacOSWindowControl(PlatformWindowControl):
    """macOS window control using tkinter attributes + pyobjc for advanced features."""

    def get_foreground_window(self):
        """Get the frontmost application's window info via pyobjc."""
        try:
            from AppKit import NSWorkspace
            
            active_app = NSWorkspace.sharedWorkspace().frontmostApplication()
            if active_app:
                app_name = active_app.localizedName()
                pid = active_app.processIdentifier()
                print(f"Frontmost app: {app_name} (PID: {pid})")
                return {
                    'app_name': str(app_name),
                    'pid': pid,
                    'bundle_id': str(active_app.bundleIdentifier() or ''),
                }
            return None
        except ImportError:
            print("pyobjc not available for window control")
            return None

    def set_always_on_top(self, window_handle, enable: bool) -> None:
        """
        For tkinter windows: use attributes('-topmost', enable).
        window_handle should be a tkinter window instance.
        """
        try:
            if hasattr(window_handle, 'attributes'):
                window_handle.attributes('-topmost', enable)
                print(f"Window topmost {'enabled' if enable else 'disabled'}")
            else:
                print("Cannot set topmost: not a tkinter window")
        except Exception as e:
            print(f"Error setting topmost: {e}")

    def set_window_opacity(self, window_handle, opacity: float) -> None:
        """Set window opacity for tkinter windows."""
        global _opacity_registry
        opacity = max(0.1, min(opacity, 1.0))
        try:
            if hasattr(window_handle, 'attributes'):
                window_handle.attributes('-alpha', opacity)
                # Track opacity by window id
                wid = id(window_handle)
                _opacity_registry[wid] = opacity
                print(f"Window opacity set to {opacity * 100:.0f}%")
            else:
                print("Cannot set opacity: not a tkinter window")
        except Exception as e:
            print(f"Error setting opacity: {e}")

    def get_window_opacity(self, window_handle) -> float:
        """Get tracked window opacity."""
        global _opacity_registry
        if window_handle is None:
            return 1.0
        wid = id(window_handle)
        return _opacity_registry.get(wid, 1.0)

    def set_click_through(self, window_handle, enable: bool) -> None:
        """
        Set click-through on a tkinter window using pyobjc.
        On macOS, this uses NSWindow.setIgnoresMouseEvents_().
        """
        try:
            from AppKit import NSApp
            
            # Get the NSWindow from tkinter's window
            if hasattr(window_handle, 'winfo_id'):
                # Try to find the NSWindow via pyobjc
                ns_window = self._get_nswindow(window_handle)
                if ns_window:
                    ns_window.setIgnoresMouseEvents_(enable)
                    print(f"Click-through {'enabled' if enable else 'disabled'}")
                    return
            
            print("Could not set click-through: NSWindow not found")
        except ImportError:
            print("pyobjc not available for click-through")
        except Exception as e:
            print(f"Error setting click-through: {e}")

    def bring_to_front(self, window_handle) -> None:
        """Bring a tkinter window to front."""
        try:
            if hasattr(window_handle, 'lift'):
                window_handle.lift()
                window_handle.focus_force()
            if hasattr(window_handle, 'attributes'):
                window_handle.attributes('-topmost', True)
                window_handle.after(100, lambda: window_handle.attributes('-topmost', False))
        except Exception as e:
            print(f"Error bringing window to front: {e}")

    def resize_window(self, window_handle, zoom_in: bool) -> None:
        """Resize a tkinter window, keeping it centered."""
        try:
            if not hasattr(window_handle, 'winfo_width'):
                return

            window_handle.update_idletasks()
            current_width = window_handle.winfo_width()
            current_height = window_handle.winfo_height()
            current_x = window_handle.winfo_x()
            current_y = window_handle.winfo_y()

            zoom_factor = 1.1 if zoom_in else 1 / 1.1
            new_width = int(current_width * zoom_factor)
            new_height = int(current_height * zoom_factor)

            min_size = 50
            if new_width < min_size or new_height < min_size:
                return

            delta_w = new_width - current_width
            delta_h = new_height - current_height
            new_x = current_x - delta_w // 2
            new_y = current_y - delta_h // 2

            window_handle.geometry(f"{new_width}x{new_height}+{new_x}+{new_y}")
        except Exception as e:
            print(f"Error resizing window: {e}")

    def get_window_info(self, window_handle) -> dict:
        """Get window info for a tkinter window."""
        try:
            if hasattr(window_handle, 'winfo_width'):
                return {
                    'x': window_handle.winfo_x(),
                    'y': window_handle.winfo_y(),
                    'width': window_handle.winfo_width(),
                    'height': window_handle.winfo_height(),
                    'title': window_handle.title() if hasattr(window_handle, 'title') else '',
                }
            return {}
        except Exception as e:
            print(f"Error getting window info: {e}")
            return {}

    def _get_nswindow(self, tk_window):
        """Get NSWindow for a tkinter window. Uses title matching (Tk 9.x compatible).

        On Tk 9.x, winfo_id() returns a pointer/handle that does NOT match
        NSWindow.windowNumber(), so we match by window title instead.
        Each Toplevel must have a unique title for this to work.
        """
        try:
            from AppKit import NSApp

            target_title = tk_window.title()
            tk_window.update_idletasks()
            for ns_win in NSApp.windows():
                if ns_win.title() == target_title:
                    return ns_win
            return None
        except Exception as e:
            print(f"Error finding NSWindow: {e}")
            return None
