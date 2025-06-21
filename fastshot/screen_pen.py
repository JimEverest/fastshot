import tkinter as tk
from pynput import keyboard
import threading
import pyautogui
from screeninfo import get_monitors
import ctypes
import win32gui
import numpy as np
import queue

class ScreenPen:
    def __init__(self, master, config):
        self.config = config
        self.master = master  # Main Tkinter root window

        # Create Toplevel window
        self.pen_window = tk.Toplevel(master)
        self.pen_window.overrideredirect(True)  # Remove window decorations
        self.pen_window.attributes('-topmost', True)  # Keep window on top
        self.pen_window.config(cursor="pencil", bg="black")  # Set cursor and background

        # Set unique window title
        self.window_title = "ScreenPenOverlay"
        self.pen_window.title(self.window_title)

        # Ensure window is created
        self.pen_window.update()

        # Create canvas
        self.canvas = tk.Canvas(self.pen_window, bg='black', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Read pen parameters from config (will be refreshed when settings change)
        self.reload_config()

        # Read highlighter parameters from config
        self.highlighter_color = self.config['ScreenPen'].get('highlighter_color', '#FFFF00')  # Default to semi-transparent yellow
        # Format: '#RRGGBBAA', where AA is alpha in hex (80 is approximately 50% transparency)

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
        print(f"Screen Pen config reloaded: color={self.pen_color}, width={self.pen_width}, opacity={self.overlay_opacity}")
    
    def update_config(self, new_config):
        """Update configuration and reload settings."""
        self.config = new_config
        self.reload_config()
        # If currently drawing, apply new settings
        if self.drawing:
            self.set_window_opacity(self.overlay_opacity)
            # Redraw with new settings
            self.redraw_all_paths()

    def start_keyboard_listener(self):
        print("Starting keyboard listener")
        # Capture hotkeys
        hotkeys = {
            self.config['Shortcuts'].get('hotkey_screenpen_toggle', '<ctrl>+x+c'): lambda: self.queue.put(self.toggle_drawing_mode),
            self.config['Shortcuts'].get('hotkey_screenpen_clear_hide', '<ctrl>+<esc>'): lambda: self.queue.put(self.clear_canvas_and_hide)
        }
        listener = keyboard.GlobalHotKeys(hotkeys)
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
        Get window handle
        """
        hwnd = win32gui.FindWindow(None, self.window_title)
        return hwnd

    def set_window_to_draw(self):
        """
        Set window to drawing mode, ensure semi-transparent state, and capture mouse events
        """
        hwnd = self.get_hwnd()
        if hwnd:
            print("Setting window to drawing mode")
            extended_style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            # Ensure WS_EX_LAYERED style is set
            extended_style = extended_style | 0x80000
            # Remove WS_EX_TRANSPARENT style
            extended_style = extended_style & ~0x20
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, extended_style)
            self.set_window_opacity(self.overlay_opacity)  # Use configurable opacity
        else:
            print("Could not find window handle to set drawing mode.")

    def set_window_opacity(self, opacity):
        """
        Use Windows API to set Tkinter window opacity
        """
        hwnd = self.get_hwnd()
        if hwnd:
            print(f"Setting window opacity to {opacity * 100}%")
            ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, int(opacity * 255), 0x2)
        else:
            print("Could not find window handle to set opacity.")

    def toggle_drawing_mode(self):
        if self.drawing:
            print("Exiting drawing mode")
            self.drawing = False
            self.set_window_transparent()
            # self.pen_window.withdraw()  # Comment out or remove this line
            # Unbind keyboard events
            self.pen_window.unbind("<Escape>")
            self.pen_window.unbind("<Control-z>")
            self.pen_window.unbind("<Control-y>")
        else:
            print("Entering drawing mode")
            self.drawing = True
            screen_info = self.get_current_screen_info()
            self.pen_window.geometry(f"{screen_info['width']}x{screen_info['height']}+{screen_info['x']}+{screen_info['y']}")
            self.pen_window.deiconify()
            self.set_window_to_draw()
            self.redraw_all_paths()
            # Bind keyboard events
            self.pen_window.focus_set()
            self.pen_window.bind("<Escape>", self.on_escape)
            self.pen_window.bind("<Control-z>", lambda event: self.undo_last_action())
            self.pen_window.bind("<Control-y>", lambda event: self.redo_last_action())


    def set_window_transparent(self):
        """
        Set window to transparent and click-through mode
        """
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
        mouse_x, mouse_y = pyautogui.position()
        for monitor in get_monitors():
            if monitor.x <= mouse_x <= monitor.x + monitor.width and monitor.y <= mouse_y <= monitor.y + monitor.height:
                print(f"Mouse is on screen: {monitor}")
                return {'x': monitor.x, 'y': monitor.y, 'width': monitor.width, 'height': monitor.height}

        # Default to primary screen
        print("Mouse is not on any screen, defaulting to primary screen.")
        screen_width, screen_height = pyautogui.size()
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
                # Reduced debug output for performance
            elif self.pen_type == 'highlighter':
                # Start drawing rectangle
                self.current_rect_start = (self.last_x, self.last_y)
                self.current_rect = None

    def on_mouse_move(self, event):
        if self.drawing:
            x, y = event.x, event.y
            if self.pen_type == 'pen':
                # Optimize: reduce print statements to avoid I/O overhead during drawing
                self.current_path.append((x, y))  # Record path points
                # Optimize: only redraw if we have enough points or sufficient distance
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
        # Reduced debug output for performance
        if self.drawing:
            if self.pen_type == 'pen' and self.current_path:
                # Finalize the current path
                smoothed_path = self.apply_catmull_rom_spline(self.current_path) if len(self.current_path) >= 4 else self.current_path
                self.undo_stack.append(('path', smoothed_path))  # Save path with type 'path'
                self.current_path = []  # Clear current path
                self.redo_stack.clear()  # Clear redo stack
                self.redraw_all_paths()  # Redraw everything
            elif self.pen_type == 'highlighter' and self.current_rect:
                # Finalize the rectangle
                rect_coords = self.canvas.coords(self.current_rect)
                self.undo_stack.append(('rectangle', rect_coords))  # Save rectangle with type 'rectangle'
                self.current_rect = None
                self.redo_stack.clear()  # Clear redo stack
                self.redraw_all_paths()  # Redraw everything

    def draw_temporary_rectangle(self, start, end):
        """
        Draw or update the temporary rectangle being drawn
        """
        # Delete previous temporary rectangle
        self.canvas.delete("current_rectangle")
        # Create new rectangle
        x1, y1 = start
        x2, y2 = end
        self.current_rect = self.canvas.create_rectangle(
            x1, y1, x2, y2,
            fill=self.highlighter_color,
            outline='',  # No outline
            stipple='gray25',  
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
            line_id = self.canvas.create_line(
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
        Redraw all saved paths and rectangles
        """
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
            self.canvas.create_line(path[i], path[i + 1], fill=self.pen_color, width=self.pen_width)

    def draw_rectangle(self, coords):
        """
        Draw a saved rectangle
        """
        self.canvas.create_rectangle(
            coords,
            fill=self.highlighter_color,
            outline='',  # No outline
            stipple='gray25'
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
        print("Clearing canvas and hiding...")
        self.clear_canvas()
        self.pen_window.withdraw()  # Hide window
        self.drawing = False  # Reset drawing mode
