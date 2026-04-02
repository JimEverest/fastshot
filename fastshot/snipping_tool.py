import tkinter as tk
from PIL import Image
import sys
import time
import mss
import mss.tools
import io
import os
# Use platform-specific monitor detection for better macOS support
from fastshot.app_platform import get_monitors

# Conditionally import win32 modules (Windows only)
_IS_WINDOWS = os.name == 'nt'
_IS_MAC = sys.platform == 'darwin'
if _IS_WINDOWS:
    try:
        import win32gui
        import win32con
        import pyautogui
    except ImportError:
        _IS_WINDOWS = False


def _get_retina_scale():
    """Get the Retina backing scale factor on macOS."""
    if not _IS_MAC:
        return 1.0
    try:
        from AppKit import NSScreen
        return NSScreen.mainScreen().backingScaleFactor() or 1.0
    except Exception:
        return 1.0


class SnippingTool:
    def __init__(self, root, monitors, on_screenshot):
        self.root = root
        self.monitors = monitors  # Keep for backward compatibility, but will be refreshed
        self.on_screenshot = on_screenshot
        self.overlays = []
        self.canvases = []
        self.rects = []

    def start_snipping(self):
        # Clear any existing overlays
        self.exit_snipping()

        # Refresh monitor information in real-time
        self.monitors = get_monitors()
        print(f"Detected {len(self.monitors)} monitors for snipping")
        for i, monitor in enumerate(self.monitors):
            print(f"Monitor {i}: {monitor.width}x{monitor.height} at ({monitor.x}, {monitor.y})")

        self.snipping = True
        self.overlays = []
        self.canvases = []
        self.rects = []

        for monitor in self.monitors:
            overlay = tk.Toplevel(self.root)
            overlay.overrideredirect(True)  # No window decorations for full-screen overlay
            overlay.title("overlay_snipping")
            overlay.geometry(f"{monitor.width}x{monitor.height}+{monitor.x}+{monitor.y}")
            overlay.configure(bg='blue')
            overlay.attributes('-alpha', 0.3)
            overlay.attributes('-topmost', True)  # Ensure the window is always on top
            overlay.bind('<Escape>', self.exit_snipping)

            canvas = tk.Canvas(overlay, cursor="cross")
            canvas.pack(fill=tk.BOTH, expand=tk.TRUE)
            canvas.bind('<ButtonPress-1>', self.on_mouse_down)
            canvas.bind('<B1-Motion>', self.on_mouse_drag)
            canvas.bind('<ButtonRelease-1>', self.on_mouse_up)

            self.overlays.append(overlay)
            self.canvases.append(canvas)
            self.rects.append(None)

            # Bring the overlay window to the front
            self.bring_window_to_front(overlay)

        self.root.update_idletasks()
        self.root.update()

        self.start_x = self.start_y = self.end_x = self.end_y = 0

    def bring_window_to_front(self, window):
        """Bring overlay window to front — platform-aware."""
        if _IS_WINDOWS:
            # Windows: use win32gui for reliable foreground activation
            try:
                hwnd = int(window.frame(), 16)
                win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                                      win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
                pyautogui.press("alt")
                win32gui.SetForegroundWindow(hwnd)
                win32gui.BringWindowToTop(hwnd)
                win32gui.SetActiveWindow(hwnd)
            except Exception as e:
                print(f"Win32 bring_to_front failed, using tkinter fallback: {e}")
                self._bring_to_front_tkinter(window)
        else:
            # macOS / Linux: use pure tkinter methods
            self._bring_to_front_tkinter(window)

    def _bring_to_front_tkinter(self, window):
        """Cross-platform bring-to-front using tkinter."""
        window.lift()
        window.focus_force()
        # On macOS, we may need to briefly set topmost to grab focus
        window.attributes('-topmost', True)
        window.after(100, lambda: window.attributes('-topmost', True))  # Keep topmost for overlay

    def exit_snipping(self, event=None):
        self.snipping = False
        for overlay in self.overlays:
            try:
                overlay.destroy()
            except Exception as e:
                print(f"Error destroying overlay: {e}")
        self.overlays = []
        self.canvases = []
        self.rects = []

    def on_mouse_down(self, event):
        self.start_x = event.x_root
        self.start_y = event.y_root
        for i in range(len(self.rects)):
            self.rects[i] = None

    def on_mouse_drag(self, event):
        for i, canvas in enumerate(self.canvases):
            if self.rects[i]:
                canvas.delete(self.rects[i])
            self.rects[i] = canvas.create_rectangle(
                self.start_x - canvas.winfo_rootx(),
                self.start_y - canvas.winfo_rooty(),
                event.x_root - canvas.winfo_rootx(),
                event.y_root - canvas.winfo_rooty(),
                outline='red'
            )

    def on_mouse_up(self, event):
        self.end_x = event.x_root
        self.end_y = event.y_root
        self.take_screenshot()
        self.exit_snipping()

    def take_screenshot(self):
        x1 = min(self.start_x, self.end_x)
        y1 = min(self.start_y, self.end_y)
        x2 = max(self.start_x, self.end_x)
        y2 = max(self.start_y, self.end_y)

        # Hide overlays and ensure they are fully hidden before capture
        for overlay in self.overlays:
            overlay.withdraw()
        self.root.update_idletasks()
        self.root.update()
        if _IS_MAC:
            # macOS needs a brief delay for window server to fully hide overlays
            time.sleep(0.15)

        # On Retina Mac, tkinter uses logical "points" but mss uses physical pixels
        scale = _get_retina_scale() if _IS_MAC else 1.0

        with mss.mss() as sct:
            monitor = {
                "top": int(y1 * scale),
                "left": int(x1 * scale),
                "width": int((x2 - x1) * scale),
                "height": int((y2 - y1) * scale)
            }
            screenshot = sct.grab(monitor)
            img = mss.tools.to_png(screenshot.rgb, screenshot.size)

        img = Image.open(io.BytesIO(img))
        img = img.convert('RGB')
        self.on_screenshot(img)
