import tkinter as tk
from pynput import keyboard
import threading
import os
import sys
from fastshot.app_platform import get_monitors
import numpy as np
import queue

# Platform-aware imports
_IS_WINDOWS = os.name == 'nt'
if _IS_WINDOWS:
    try:
        import ctypes
        import win32gui
        import pyautogui
    except ImportError:
        _IS_WINDOWS = False
else:
    try:
        import pyautogui
    except ImportError:
        pyautogui = None

class ScreenPen:
    def __init__(self, master, config):
        self.config = config
        self.master = master  # Main Tkinter root window
        self._is_mac = sys.platform == 'darwin'

        # Set unique window title
        self.window_title = "ScreenPenOverlay"

        # Single window for both platforms — no overlay_window needed
        self.pen_window = tk.Toplevel(master)
        self.pen_window.overrideredirect(True)
        self.pen_window.attributes('-topmost', True)
        self.pen_window.config(cursor="pencil", bg="black")
        self.pen_window.title(self.window_title)
        self.pen_window.update()

        # Create canvas
        self.canvas = tk.Canvas(self.pen_window, bg='black', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # macOS: holds the darkened desktop PhotoImage (prevents GC)
        self._bg_photo = None
        # macOS: holds highlight PhotoImages to prevent GC
        self._highlight_photos = []
        self._temp_highlight_photo = None

        # Read pen parameters from config (will be refreshed when settings change)
        self.reload_config()

        self.drawing = False  # Initial state is not drawing
        self.pen_type = 'pen'  # Start with normal pen
        self.current_rect = None  # For Highlighter rectangle

        # Initialize undo and redo stacks
        self.undo_stack = []  # Stores completed paths
        self.redo_stack = []  # Stores undone paths
        self.current_path = []  # Current drawing path
        self.rectangles = []  # Stores drawn rectangles

        # Initially hide the window
        self.pen_window.withdraw()

        # Mouse event bindings
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.canvas.bind("<Button-3>", self.toggle_pen_type)  # Right-click to toggle pen type

        # Initialize queue for thread communication
        self.queue = queue.Queue()

    def reload_config(self):
        """Reload configuration from config file."""
        self.pen_color = self.config['ScreenPen'].get('pen_color', 'red')
        self.pen_width = self.config['ScreenPen'].getint('pen_width', 3)
        self.smooth_factor = self.config['ScreenPen'].getint('smooth_factor', 3)
        # Read overlay transparency setting (default 40%)
        self.overlay_opacity = self.config['ScreenPen'].getfloat('overlay_opacity', 0.4)
        # Read highlighter color and opacity
        self.highlighter_color = self.config['ScreenPen'].get('highlighter_color', '#FFFF00')
        self.highlighter_opacity = self.config['ScreenPen'].getfloat('highlighter_opacity', 0.25)
        print(f"Screen Pen config reloaded: color={self.pen_color}, width={self.pen_width}, opacity={self.overlay_opacity}, hl_color={self.highlighter_color}, hl_opacity={self.highlighter_opacity}")

    def update_config(self, new_config):
        """Update configuration and reload settings."""
        self.config = new_config
        self.reload_config()
        # If currently drawing, apply new settings
        if self.drawing:
            self.set_window_opacity(self.overlay_opacity)
            # Redraw with new settings
            self.redraw_all_paths()

    def _get_stipple(self):
        """Map highlighter_opacity to the closest tkinter stipple pattern (Windows)."""
        op = self.highlighter_opacity
        if op <= 0.18:
            return 'gray12'
        elif op <= 0.37:
            return 'gray25'
        elif op <= 0.62:
            return 'gray50'
        else:
            return 'gray75'

    def _create_highlight_image(self, width, height):
        """Create a semi-transparent highlight PIL PhotoImage (macOS)."""
        from PIL import Image, ImageTk
        color = self.highlighter_color.lstrip('#')
        r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
        alpha = int(self.highlighter_opacity * 255)
        img = Image.new('RGBA', (max(1, abs(width)), max(1, abs(height))), (r, g, b, alpha))
        return ImageTk.PhotoImage(img)

    def _undo_if_drawing(self):
        if self.drawing:
            self.undo_last_action()

    def _redo_if_drawing(self):
        if self.drawing:
            self.redo_last_action()

    def start_keyboard_listener(self):
        print("Starting keyboard listener")
        from pynput.keyboard import Key, KeyCode, HotKey, Listener, _NORMAL_MODIFIERS

        toggle_combo = self.config['Shortcuts'].get('hotkey_screenpen_toggle', '<ctrl>+x+c')
        clear_combo = self.config['Shortcuts'].get('hotkey_screenpen_clear_hide', '<ctrl>+<esc>')

        hk_toggle = HotKey(HotKey.parse(toggle_combo),
                           lambda: self.queue.put(self.toggle_drawing_mode))
        hk_clear = HotKey(HotKey.parse(clear_combo),
                          lambda: self.queue.put(self.clear_canvas_and_hide))

        # Undo/redo via pynput (tkinter bindings don't work on macOS overrideredirect windows)
        hk_undo_ctrl = HotKey(HotKey.parse('<ctrl>+z'),
                              lambda: self.queue.put(self._undo_if_drawing))
        hk_redo_ctrl = HotKey(HotKey.parse('<ctrl>+y'),
                              lambda: self.queue.put(self._redo_if_drawing))
        all_hotkeys = [hk_toggle, hk_clear, hk_undo_ctrl, hk_redo_ctrl]

        if self._is_mac:
            hk_undo_cmd = HotKey(HotKey.parse('<cmd>+z'),
                                 lambda: self.queue.put(self._undo_if_drawing))
            hk_redo_cmd = HotKey(HotKey.parse('<cmd>+y'),
                                 lambda: self.queue.put(self._redo_if_drawing))
            all_hotkeys.extend([hk_undo_cmd, hk_redo_cmd])

        # Track modifier state so we can distinguish bare ESC from Ctrl+ESC.
        modifiers_held = set()
        _modifier_keys = {Key.ctrl, Key.ctrl_l, Key.ctrl_r,
                          Key.cmd, Key.cmd_l, Key.cmd_r,
                          Key.alt, Key.alt_l, Key.alt_r,
                          Key.shift, Key.shift_l, Key.shift_r}

        def _canonical(key):
            if isinstance(key, KeyCode):
                if key.char is not None and key.char.isprintable():
                    return KeyCode.from_char(key.char.lower())
                elif key.vk is not None:
                    return KeyCode.from_vk(key.vk)
                return key
            elif isinstance(key, Key) and key.value in _NORMAL_MODIFIERS:
                return _NORMAL_MODIFIERS[key.value]
            elif isinstance(key, Key) and hasattr(key.value, 'vk') and key.value.vk is not None:
                return KeyCode.from_vk(key.value.vk)
            return key

        def on_press(key):
            try:
                if key in _modifier_keys:
                    modifiers_held.add(key)
                ck = _canonical(key)
                for hk in all_hotkeys:
                    hk.press(ck)
                # Plain ESC (no modifiers held) -> temporary exit
                if key == Key.esc and not modifiers_held:
                    self.queue.put(self.on_escape)
            except Exception:
                pass

        def on_release(key):
            try:
                modifiers_held.discard(key)
                ck = _canonical(key)
                for hk in all_hotkeys:
                    hk.release(ck)
            except Exception:
                pass

        listener = Listener(on_press=on_press, on_release=on_release)
        listener.daemon = True
        listener.start()

        # Start processing queue tasks
        self.process_queue()

    def process_queue(self):
        try:
            while True:
                func = self.queue.get_nowait()
                func()  # Execute function in main thread
        except queue.Empty:
            pass
        self.master.after(50, self.process_queue)  # Check queue every 50ms

    def get_hwnd(self):
        """
        Get window handle (Windows only)
        """
        if _IS_WINDOWS:
            hwnd = win32gui.FindWindow(None, self.window_title)
            return hwnd
        return None

    def _capture_darkened_desktop(self, screen_info):
        """Capture the desktop and darken it for the overlay effect (macOS)."""
        import mss
        from PIL import Image, ImageEnhance, ImageTk

        with mss.mss() as sct:
            monitor = {
                "top": screen_info['y'],
                "left": screen_info['x'],
                "width": screen_info['width'],
                "height": screen_info['height'],
            }
            screenshot = sct.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)

        # Darken: overlay_opacity=0.3 means 30% black -> 70% brightness
        enhancer = ImageEnhance.Brightness(img)
        darkened = enhancer.enhance(1.0 - self.overlay_opacity)

        # On Retina displays, mss captures physical pixels but tkinter
        # uses logical points. Scale down by backingScaleFactor.
        try:
            from AppKit import NSScreen
            scale = int(NSScreen.mainScreen().backingScaleFactor())
            if scale > 1:
                logical_size = (img.width // scale, img.height // scale)
                darkened = darkened.resize(logical_size, Image.LANCZOS)
        except Exception:
            pass

        self._bg_photo = ImageTk.PhotoImage(darkened)
        return self._bg_photo

    def set_window_to_draw(self):
        """
        Set window to drawing mode, ensure semi-transparent state, and capture mouse events
        """
        if _IS_WINDOWS:
            hwnd = self.get_hwnd()
            if hwnd:
                print("Setting window to drawing mode (Windows)")
                extended_style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
                extended_style = extended_style | 0x80000  # WS_EX_LAYERED
                extended_style = extended_style & ~0x20     # Remove WS_EX_TRANSPARENT
                ctypes.windll.user32.SetWindowLongW(hwnd, -20, extended_style)
                self.set_window_opacity(self.overlay_opacity)
            else:
                print("Could not find window handle to set drawing mode.")
        else:
            # macOS: screenshot approach handles overlay, just set alpha to full
            self.pen_window.attributes('-alpha', 1.0)

    def set_window_opacity(self, opacity):
        """
        Set window opacity — cross-platform
        """
        if _IS_WINDOWS:
            hwnd = self.get_hwnd()
            if hwnd:
                print(f"Setting window opacity to {opacity * 100}% (Windows)")
                ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, int(opacity * 255), 0x2)
            else:
                print("Could not find window handle to set opacity.")
        else:
            # macOS: re-capture and re-darken desktop
            if self.drawing:
                print(f"Setting window opacity to {opacity * 100}% (macOS)")
                screen_info = self.get_current_screen_info()
                bg_photo = self._capture_darkened_desktop(screen_info)
                self.canvas.delete("bg_overlay")
                self.canvas.create_image(0, 0, anchor='nw',
                                         image=bg_photo, tags="bg_overlay")
                self.canvas.tag_lower("bg_overlay")
                self.redraw_all_paths()

    def toggle_drawing_mode(self):
        if self.drawing:
            print("Exiting drawing mode")
            self.drawing = False
            if self._is_mac:
                self.pen_window.withdraw()  # Just hide — no click-through needed
            else:
                self.set_window_transparent()  # Windows: existing behavior
            # Unbind keyboard events
            self.pen_window.unbind("<Escape>")
        else:
            print("Entering drawing mode")
            self.drawing = True
            screen_info = self.get_current_screen_info()
            geom = f"{screen_info['width']}x{screen_info['height']}+{screen_info['x']}+{screen_info['y']}"

            if self._is_mac:
                # Capture desktop BEFORE showing the overlay
                bg_photo = self._capture_darkened_desktop(screen_info)

            self.pen_window.geometry(geom)
            self.pen_window.deiconify()

            if self._is_mac:
                self.pen_window.attributes('-alpha', 1.0)
                self.canvas.delete("bg_overlay")
                self.canvas.create_image(0, 0, anchor='nw',
                                         image=bg_photo, tags="bg_overlay")
                self.canvas.tag_lower("bg_overlay")  # Push behind strokes
            else:
                self.set_window_to_draw()  # Windows: existing behavior

            self.redraw_all_paths()
            self.pen_window.focus_set()
            self.pen_window.bind("<Escape>", self.on_escape)


    def set_window_transparent(self):
        """
        Set window to transparent and click-through mode (Windows only)
        """
        if _IS_WINDOWS:
            hwnd = self.get_hwnd()
            if hwnd:
                print("Setting window transparent and click-through")
                extended_style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
                extended_style = extended_style | 0x80000 | 0x20  # Set transparent and click-through
                ctypes.windll.user32.SetWindowLongW(hwnd, -20, extended_style)
                ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, 0, 0x1)
            else:
                print("Could not find window handle to set transparency.")

    def on_escape(self, event=None):
        if self.drawing:
            self.toggle_drawing_mode()

    def get_current_screen_info(self):
        """
        Get the dimensions and position of the screen where the mouse is currently located
        """
        try:
            if pyautogui:
                mouse_x, mouse_y = pyautogui.position()
            else:
                mouse_x = self.master.winfo_pointerx()
                mouse_y = self.master.winfo_pointery()
        except Exception:
            mouse_x = self.master.winfo_pointerx()
            mouse_y = self.master.winfo_pointery()

        for monitor in get_monitors():
            if monitor.x <= mouse_x <= monitor.x + monitor.width and monitor.y <= mouse_y <= monitor.y + monitor.height:
                print(f"Mouse is on screen: {monitor}")
                return {'x': monitor.x, 'y': monitor.y, 'width': monitor.width, 'height': monitor.height}

        # Default to primary screen
        print("Mouse is not on any screen, defaulting to primary screen.")
        try:
            if pyautogui:
                screen_width, screen_height = pyautogui.size()
            else:
                screen_width = self.master.winfo_screenwidth()
                screen_height = self.master.winfo_screenheight()
        except Exception:
            screen_width = self.master.winfo_screenwidth()
            screen_height = self.master.winfo_screenheight()
        return {'x': 0, 'y': 0, 'width': screen_width, 'height': screen_height}

    def toggle_pen_type(self, event=None):
        """
        Toggle between normal pen and highlighter
        """
        if self.pen_type == 'pen':
            self.pen_type = 'highlighter'
            self.pen_window.config(cursor="cross")  # Change cursor to crosshair
            print("Switched to Highlighter mode")
        else:
            self.pen_type = 'pen'
            self.pen_window.config(cursor="pencil")  # Change cursor back to pencil
            print("Switched to Pen mode")

    def on_button_press(self, event):
        if self.drawing:
            self.last_x, self.last_y = event.x, event.y
            if self.pen_type == 'pen':
                self.current_path = [(self.last_x, self.last_y)]  # Start a new path
            elif self.pen_type == 'highlighter':
                # Start drawing rectangle
                self.current_rect_start = (self.last_x, self.last_y)
                self.current_rect = None

    def on_mouse_move(self, event):
        if self.drawing:
            x, y = event.x, event.y
            if self.pen_type == 'pen':
                self.current_path.append((x, y))  # Record path points
                if len(self.current_path) == 1 or self._should_redraw(x, y):
                    self.redraw_current_path_optimized()  # Use optimized redraw
            elif self.pen_type == 'highlighter':
                # Update rectangle
                self.draw_temporary_rectangle(self.current_rect_start, (x, y))

    def _should_redraw(self, x, y):
        """Determine if we should redraw based on distance from last drawn point."""
        if len(self.current_path) < 2:
            return True

        # Only redraw if mouse moved sufficient distance (reduces lag)
        last_x, last_y = self.current_path[-2]
        distance = ((x - last_x) ** 2 + (y - last_y) ** 2) ** 0.5
        return distance > 2  # Minimum 2 pixel movement threshold

    def on_button_release(self, event):
        if self.drawing:
            if self.pen_type == 'pen' and self.current_path:
                # Finalize the current path
                smoothed_path = self.apply_catmull_rom_spline(self.current_path) if len(self.current_path) >= 4 else self.current_path
                self.undo_stack.append(('path', smoothed_path))  # Save path with type 'path'
                self.current_path = []  # Clear current path
                self.redo_stack.clear()  # Clear redo stack
                self.redraw_all_paths()  # Redraw everything
            elif self.pen_type == 'highlighter' and self.current_rect:
                # Finalize the rectangle — store raw start/end coords
                x1, y1 = self.current_rect_start
                x2, y2 = event.x, event.y
                rect_coords = [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]
                self.undo_stack.append(('rectangle', rect_coords))
                self.current_rect = None
                self._temp_highlight_photo = None
                self.redo_stack.clear()
                self.redraw_all_paths()

    def draw_temporary_rectangle(self, start, end):
        """
        Draw or update the temporary rectangle being drawn
        """
        # Delete previous temporary rectangle
        self.canvas.delete("current_rectangle")
        x1, y1 = start
        x2, y2 = end
        if self._is_mac:
            # Use PIL RGBA image for true transparency (stipple broken on Tk 9.x Metal)
            w, h = abs(x2 - x1), abs(y2 - y1)
            if w > 0 and h > 0:
                self._temp_highlight_photo = self._create_highlight_image(w, h)
                self.current_rect = self.canvas.create_image(
                    min(x1, x2), min(y1, y2), anchor='nw',
                    image=self._temp_highlight_photo, tags="current_rectangle"
                )
        else:
            self.current_rect = self.canvas.create_rectangle(
                x1, y1, x2, y2,
                fill=self.highlighter_color,
                outline='',
                stipple=self._get_stipple(),
                tags="current_rectangle"
            )

    def redraw_current_path(self):
        """
        Redraw the current path being drawn
        """
        # Delete current path drawing
        self.canvas.delete("current_line")

        # Draw smoothed path
        if len(self.current_path) >= 4:
            smooth_path = self.apply_catmull_rom_spline(self.current_path)
            for i in range(len(smooth_path) - 1):
                self.canvas.create_line(smooth_path[i], smooth_path[i + 1], fill=self.pen_color, width=self.pen_width, tags="current_line")
        else:
            # Draw raw path if not enough points for spline
            for i in range(len(self.current_path) - 1):
                self.canvas.create_line(self.current_path[i], self.current_path[i + 1], fill=self.pen_color, width=self.pen_width, tags="current_line")

    def redraw_current_path_optimized(self):
        """
        Optimized redraw method to reduce lag during drawing
        """
        # Only redraw the latest segment instead of the entire path
        if len(self.current_path) >= 2:
            # For real-time drawing, just draw the latest segment
            last_point = self.current_path[-2]
            current_point = self.current_path[-1]

            # Create a line from the last point to current point
            self.canvas.create_line(
                last_point, current_point,
                fill=self.pen_color,
                width=self.pen_width,
                tags="current_line"
            )

            # Keep track of line segments to avoid too many objects
            # Every 10 segments, consolidate by redrawing the full path
            if len(self.current_path) % 10 == 0:
                self.redraw_current_path()

    def apply_catmull_rom_spline(self, points):
        """
        Apply optimized Catmull-Rom spline to smooth the path
        """
        # Reduce computation by using fewer interpolation points during real-time drawing
        smooth_factor = max(1, self.smooth_factor // 2) if len(points) > 20 else self.smooth_factor

        def catmull_rom(p0, p1, p2, p3, t):
            """
            Catmull-Rom spline formula
            """
            t2 = t * t
            t3 = t2 * t
            return (
                0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3),
                0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            )

        # Generate spline points with adaptive smoothing
        smooth_points = []
        step_size = max(1, len(points) // 50)  # Adaptive step size for large paths

        for i in range(0, len(points) - 3, step_size):
            if i + 3 < len(points):
                p0, p1, p2, p3 = points[i], points[i + 1], points[i + 2], points[i + 3]
                for t in np.linspace(0, 1, smooth_factor):
                    smooth_points.append(catmull_rom(p0, p1, p2, p3, t))

        return smooth_points if smooth_points else points

    def redraw_all_paths(self):
        """
        Redraw all saved paths and rectangles.
        On macOS, preserves bg_overlay; on Windows, clears all.
        """
        if self._is_mac:
            # Delete only strokes, preserve bg_overlay
            self.canvas.delete("stroke")
            self.canvas.delete("current_line")
            self.canvas.delete("current_rectangle")
            self._highlight_photos = []  # Clear old refs, rebuild below
        else:
            self.canvas.delete("all")  # Clear canvas

        for item_type, item_data in self.undo_stack:
            if item_type == 'path':
                self.draw_path(item_data)
            elif item_type == 'rectangle':
                self.draw_rectangle(item_data)
        self.redraw_current_path()  # Redraw current path

    def draw_path(self, path):
        """
        Draw a saved path
        """
        if len(path) < 2:
            return
        for i in range(len(path) - 1):
            self.canvas.create_line(path[i], path[i + 1], fill=self.pen_color, width=self.pen_width, tags="stroke")

    def draw_rectangle(self, coords):
        """
        Draw a saved rectangle
        """
        if self._is_mac:
            x1, y1, x2, y2 = coords
            w, h = int(x2 - x1), int(y2 - y1)
            if w > 0 and h > 0:
                photo = self._create_highlight_image(w, h)
                self._highlight_photos.append(photo)  # Prevent GC
                self.canvas.create_image(x1, y1, anchor='nw',
                                         image=photo, tags="stroke")
        else:
            self.canvas.create_rectangle(
                coords,
                fill=self.highlighter_color,
                outline='',
                stipple=self._get_stipple(),
                tags="stroke"
            )

    def undo_last_action(self):
        if self.undo_stack:
            print("Undo last action")
            last_item = self.undo_stack.pop()  # Pop last item
            self.redo_stack.append(last_item)  # Push to redo stack
            self.redraw_all_paths()  # Redraw everything

    def redo_last_action(self):
        if self.redo_stack:
            print("Redo last action")
            last_item = self.redo_stack.pop()
            self.undo_stack.append(last_item)  # Push back to undo stack
            self.redraw_all_paths()  # Redraw everything

    def clear_canvas(self, keep_history=False):
        print("Clearing canvas...")
        self.canvas.delete("all")  # Clear canvas
        if not keep_history:
            self.undo_stack.clear()  # Clear undo stack
            self.redo_stack.clear()  # Clear redo stack

    def clear_canvas_and_hide(self):
        """Clear all strokes/highlights and fully hide Screen Pen."""
        print("Clearing canvas and hiding...")
        self.clear_canvas()
        if self._is_mac:
            self.canvas.delete("bg_overlay")
            self._bg_photo = None
            self._highlight_photos = []
            self._temp_highlight_photo = None
        self.drawing = False
        self.pen_type = 'pen'
        self.pen_window.config(cursor="pencil")
        self.pen_window.unbind("<Escape>")
        self.pen_window.withdraw()
