import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
import io
import win32clipboard
from pynput import keyboard
import os
import ctypes # Import ctypes if not already present
import time # Add time import

from .paint_tool import PaintTool
from .text_tool import TextTool
from .ask_dialog import AskDialog  # 导入 AskDialog 类
from .utils.llm_utils import LLMExtractor, ExtractResultDialog

# --- New Class: ZoomIndicator ---
class ZoomIndicator(tk.Toplevel):
    """A temporary, semi-transparent indicator for zoom percentage with fade-out."""
    def __init__(self, parent_window, scale):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.overrideredirect(True)
        self.attributes('-topmost', True)

        self.initial_alpha = 0.75
        self.current_alpha = self.initial_alpha
        self.attributes('-alpha', self.current_alpha)

        # Make window non-interactive (click-through) - Windows specific
        # This WS_EX_TRANSPARENT style makes the window ignore mouse events (clicks, scroll),
        # passing them to the window underneath (the ImageWindow).
        if os.name == 'nt':
            self.after(10, self._set_click_through) # Delay needed for HWND

        self.label = tk.Label(self, font=("Arial", 16, "bold"), bg="#222222", fg="white", padx=10, pady=5)
        self.label.pack()

        self.update_scale(scale) # Initial text and position

        # --- Fade Out Logic ---
        self.fade_duration = 1000  # milliseconds (2 seconds)
        self.fade_steps = 40       # Number of steps for the fade
        self.fade_interval = self.fade_duration // self.fade_steps # ms per step
        self.fade_start_time = time.time()
        self.fade_job = None
        self.start_fade_out()
        # --- End Fade Out Logic ---

    def _set_click_through(self):
        """Set WS_EX_TRANSPARENT style for click-through."""
        try:
            hwnd = self.winfo_id()
            # Get current extended window style
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20) # GWL_EXSTYLE
            # Add WS_EX_LAYERED and WS_EX_TRANSPARENT styles
            style = style | 0x80000 | 0x20 # WS_EX_LAYERED | WS_EX_TRANSPARENT
            # Set the new extended window style
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style)
            # Set initial layered window attributes (needed for alpha)
            ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, int(self.current_alpha * 255), 0x2) # LWA_ALPHA
        except Exception as e:
            print(f"Error setting click-through for ZoomIndicator: {e}")

    def update_scale(self, scale):
        """Updates the displayed scale and repositions the indicator."""
        percentage = max(1, int(scale * 100)) # Ensure at least 1%
        self.label.config(text=f"{percentage}%")

        # Recalculate position to center on parent window
        self.update_idletasks() # Ensure indicator size is calculated
        # Check if parent window still exists before getting geometry
        if not self.parent_window.winfo_exists():
             self.destroy() # Destroy indicator if parent is gone
             return

        parent_x = self.parent_window.winfo_x()
        parent_y = self.parent_window.winfo_y()
        parent_width = self.parent_window.winfo_width()
        parent_height = self.parent_window.winfo_height()
        indicator_width = self.winfo_width()
        indicator_height = self.winfo_height()

        # x_pos = parent_x + (parent_width // 2) - (indicator_width // 2)
        # y_pos = parent_y + (parent_height // 2) - (indicator_height // 2)
        x_pos = parent_x +parent_width
        y_pos = parent_y 
        self.geometry(f"+{x_pos}+{y_pos}")

    def start_fade_out(self):
        """Initiates the fade-out process."""
        if self.fade_job:
            self.after_cancel(self.fade_job) # Cancel previous fade if any

        self.fade_start_time = time.time()
        self.current_alpha = self.initial_alpha # Reset alpha
        self.attributes('-alpha', self.current_alpha)
        self._fade_step() # Start the recursive fade steps

    def _fade_step(self):
        """Performs a single step of the fade-out animation."""
        elapsed_time = (time.time() - self.fade_start_time) * 1000 # milliseconds
        progress = min(elapsed_time / self.fade_duration, 1.0) # Ensure progress doesn't exceed 1

        self.current_alpha = self.initial_alpha * (1.0 - progress)

        try:
            # Update window alpha
            if self.winfo_exists():
                 self.attributes('-alpha', max(0.0, self.current_alpha)) # Ensure alpha doesn't go below 0
            else:
                 return # Stop if window destroyed

            if progress < 1.0:
                # Schedule the next step
                self.fade_job = self.after(self.fade_interval, self._fade_step)
            else:
                # Fade complete, destroy the window
                self.destroy()
        except tk.TclError as e:
             # Handle cases where the window might be destroyed unexpectedly
             print(f"TclError during fade step (window likely destroyed): {e}")
             self.destroy()

    def reset_fade_timer(self):
        """Resets the fade-out timer when zoom happens again."""
        # No need to cancel here, start_fade_out handles it
        self.start_fade_out()

    def destroy(self):
        """Destroys the indicator window and cancels any pending fade job."""
        if self.fade_job:
            self.after_cancel(self.fade_job)
            self.fade_job = None
        # Clear the reference in the parent ImageWindow
        if hasattr(self.parent_window, 'zoom_indicator_ref') and self.parent_window.zoom_indicator_ref == self:
             self.parent_window.zoom_indicator_ref = None
        # Check if window exists before destroying
        if self.winfo_exists():
            super().destroy()

class ImageWindow:
    def __init__(self, app, img, config):
        self.app = app
        self.config = config
        self.root = app.root
        self.img_window = tk.Toplevel(self.root)
        self.img_window.overrideredirect(True)
        self.img_window.attributes('-topmost', True)
        self.img_window.bind('<ButtonPress-1>', self.start_move)
        self.img_window.bind('<B1-Motion>', self.do_move)
        self.img_window.bind('<Button-3>', self.show_context_menu)
        self.img_window.bind('<MouseWheel>', self.zoom)
        self.img_window.bind('<Enter>', self.activate_window)

        self.img_label = tk.Label(self.img_window, borderwidth=1, relief="solid")
        self.img_label.pack()
        self.update_image(img)

        self.paint_tool = PaintTool(self)
        self.text_tool = TextTool(self)
        self.draw_history = []
        self.ask_dialog = None  # 添加 AskDialog 的实例变量
        self.is_dialog_open = False  # 用于禁用截图交互
        self.llm_extractor = LLMExtractor()
        self.is_hidden = False # Track visibility state
        self.zoom_indicator_ref = None # Reference to the zoom indicator

        self.setup_hotkey_listener()

    def setup_hotkey_listener(self):
        def on_activate_paint():
            self.app.exit_all_modes()
            if self.img_window.winfo_exists():
                self.paint_tool.enable_paint_mode()

        def on_activate_text():
            self.app.exit_all_modes()
            if self.img_window.winfo_exists():
                self.text_tool.enable_text_mode()

        def for_canonical(f):
            return lambda k: f(self.listener.canonical(k))

        # 从配置文件获取快捷键
        hotkey_paint_str = self.config['Shortcuts'].get('hotkey_paint', '<ctrl>+p')
        hotkey_text_str = self.config['Shortcuts'].get('hotkey_text', '<ctrl>+t')

        hotkey_paint = keyboard.HotKey(keyboard.HotKey.parse(hotkey_paint_str), on_activate_paint)
        hotkey_text = keyboard.HotKey(keyboard.HotKey.parse(hotkey_text_str), on_activate_text)

        self.listener = keyboard.Listener(
            on_press=for_canonical(hotkey_paint.press),
            on_release=for_canonical(hotkey_paint.release))
        self.listener.start()

        self.listener_text = keyboard.Listener(
            on_press=for_canonical(hotkey_text.press),
            on_release=for_canonical(hotkey_text.release))
        self.listener_text.start()

    def set_paint_tool(self, paint_tool):
        if self.paint_tool and self.paint_tool != paint_tool:
            self.paint_tool.disable_paint_mode()
        self.paint_tool = paint_tool

    def set_text_tool(self, text_tool):
        if self.text_tool and self.text_tool != text_tool:
            self.text_tool.disable_text_mode()
        self.text_tool = text_tool

    def update_image(self, img):
        self.img_label.original_image = img
        self.img_label.zoomed_image = img.copy()
        self.img_label.scale = 1.0
        self.img_label.image = ImageTk.PhotoImage(img)
        self.img_label.config(image=self.img_label.image)

    def start_move(self, event):
        if not self.paint_tool.painting and not self.text_tool.text_mode:
            self.img_window._drag_data = {"x": event.x, "y": event.y}

    def do_move(self, event):
        if not self.paint_tool.painting and not self.text_tool.text_mode and not self.is_dialog_open:
            x = self.img_window.winfo_x() + event.x - self.img_window._drag_data["x"]
            y = self.img_window.winfo_y() + event.y - self.img_window._drag_data["y"]
            self.img_window.geometry(f"+{x}+{y}")
            # 更新对话图标的位置
            if self.ask_dialog and self.ask_dialog.is_minimized:
                self.ask_dialog.update_dialog_icon_position()

    def show_context_menu(self, event):
        self.create_context_menu()
        self.context_menu.post(event.x_root, event.y_root)

    def create_context_menu(self):
        self.context_menu = tk.Menu(self.img_window, tearoff=0)
        
        # 使用 Unicode 字符作为图标
        icons = {
            "Copy": "📋",
            "Close": "❌",
            "Save As...": "💾",
            "Paint": "🎨",
            "Undo": "↺",
            "Exit Edit": "🚪",
            "Text": "📝",
            "Rotate Left": "↶",        # 新增：逆时针旋转图标
            "Rotate Right": "↷",       # 新增：顺时针旋转图标
            "OCR": "🧾",
            "Ask": "💬",
            "PowerExtract": "🔍"
        }

        commands = {
            "Copy": self.copy,
            "Close": self.close,
            "Save As...": self.save_as,
            "Paint": self.paint,
            "Undo": self.undo,
            "Exit Edit": self.exit_edit_mode,
            "Text": self.text,
            "Rotate Left": self.rotate_left,    # 新增：逆时针旋转命令
            "Rotate Right": self.rotate_right,  # 新增：顺时针旋转命令
            "OCR": self.ocr,
            "Ask": self.open_ask_dialog,
            "PowerExtract": self.power_extract
        }

        for label, icon in icons.items():
            self.context_menu.add_command(label=f"{icon} {label}", command=commands[label])
            
        # 添加分隔符和设置选项
        self.context_menu.add_separator()
        self.context_menu.add_command(label="⚙️ LLM Settings", command=self.show_llm_settings)

    def close(self):
        # Ensure zoom indicator is destroyed if the window is closed
        if self.zoom_indicator_ref and self.zoom_indicator_ref.winfo_exists():
            self.zoom_indicator_ref.destroy()
            self.zoom_indicator_ref = None

        if self.ask_dialog and self.ask_dialog.dialog_window and self.ask_dialog.dialog_window.winfo_exists():
            self.ask_dialog.clean_and_close()
        # Destroy the window first
        was_hidden = self.is_hidden
        self.img_window.destroy()
        # Remove from the app's list
        if self in self.app.windows:
            self.app.windows.remove(self)
        # Update indicator if windows are hidden and this window was part of the count
        if self.app.all_windows_hidden and was_hidden:
             self.app.update_indicator_on_close()

    def save_as(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")])
        if file_path:
            self.img_label.zoomed_image.save(file_path)

    def paint(self):
        self.paint_tool.enable_paint_mode()

    def undo(self):
        self.paint_tool.undo_last_draw()

    def exit_edit_mode(self):
        if self.img_window.winfo_exists():
            self.paint_tool.disable_paint_mode()
            self.text_tool.disable_text_mode()

    # 新增方法
    def open_ask_dialog(self):
        if self.ask_dialog and self.ask_dialog.dialog_window and self.ask_dialog.dialog_window.winfo_exists():
            if self.ask_dialog.is_minimized:
                self.ask_dialog.maximize_dialog()
            else:
                self.ask_dialog.dialog_window.lift()
        else:
            self.ask_dialog = AskDialog(self)
            self.is_dialog_open = True

    # def disable_interactions(self):
    #     # 禁用截图的移动和缩放功能
    #     self.img_window.unbind('<ButtonPress-1>')
    #     self.img_window.unbind('<B1-Motion>')
    #     self.img_window.unbind('<MouseWheel>')

    # def enable_interactions(self):
    #     # 恢复截图的移动和缩放功能
    #     self.img_window.bind('<ButtonPress-1>', self.start_move)
    #     self.img_window.bind('<B1-Motion>', self.do_move)
    #     self.img_window.bind('<MouseWheel>', self.zoom)

    def copy(self):
        output = io.BytesIO()
        self.img_label.zoomed_image.save(output, format='BMP')
        data = output.getvalue()[14:]
        output.close()

        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        win32clipboard.CloseClipboard()

    def text(self):
        self.text_tool.enable_text_mode()

    def ocr(self):
        plugin = self.app.plugins.get('fastshot.plugin_ocr')
        if plugin:
            img_path = 'temp.png'
            self.img_label.zoomed_image.save(img_path)
            result = plugin.ocr(img_path)
            plugin.show_message("OCR result updated in clipboard", self.img_window)

    def zoom(self, event):
        if not self.is_dialog_open:
            scale_factor = 1.1 if event.delta > 0 else 0.9

            last_scale = self.img_label.scale
            new_scale = last_scale * scale_factor
            # Clamp scale between reasonable limits (e.g., 10% to 1000%)
            new_scale = max(0.05, min(new_scale, 10.0))

            # # Only update if scale actually changes significantly
            # if abs(new_scale - last_scale) < 0.01 and new_scale != 0.1 and new_scale != 10.0:
            #      return # Avoid tiny changes causing updates

            if new_scale >= 0.8:
                self.img_label.scale = round(new_scale, 1)
            else:
                self.img_label.scale = new_scale

            print("self.img_label.scale:  ", self.img_label.scale)
            new_width = int(self.img_label.original_image.width * self.img_label.scale)
            new_height = int(self.img_label.original_image.height * self.img_label.scale)

            # Check for excessively large dimensions to prevent memory errors
            max_dimension = 16000 # Example limit, adjust as needed
            if new_width > max_dimension or new_height > max_dimension:
                print(f"Zoom limit reached to prevent excessive size ({new_width}x{new_height}).")
                self.img_label.scale = last_scale # Revert scale
                return

            try:
                self.img_label.zoomed_image = self.img_label.original_image.resize((new_width, new_height), Image.LANCZOS)
                self.redraw_image() # This will update the label's image

                # --- Zoom Indicator Logic ---
                if self.zoom_indicator_ref and self.zoom_indicator_ref.winfo_exists():
                    # Update existing indicator and reset timer
                    self.zoom_indicator_ref.update_scale(self.img_label.scale)
                    self.zoom_indicator_ref.reset_fade_timer()
                else:
                    # Create new indicator
                    self.zoom_indicator_ref = ZoomIndicator(self.img_window, self.img_label.scale)
                # --- End Zoom Indicator Logic ---

            except MemoryError:
                print("MemoryError during image resize. Reverting scale.")
                self.img_label.scale = last_scale # Revert scale on error
            except Exception as e:
                print(f"Error during zoom resize: {e}")
                self.img_label.scale = last_scale # Revert scale on other errors

    def redraw_image(self):
        self.img_label.zoomed_image = self.img_label.original_image.resize(
            (int(self.img_label.original_image.width * self.img_label.scale),
             int(self.img_label.original_image.height * self.img_label.scale)),
            Image.LANCZOS
        )
        draw = ImageDraw.Draw(self.img_label.zoomed_image)
        for item in self.draw_history:
            if isinstance(item, list):  # 画线的历史记录
                for (x1, y1, x2, y2) in item:
                    scaled_x1 = int(x1 * self.img_label.scale)
                    scaled_y1 = int(y1 * self.img_label.scale)
                    scaled_x2 = int(x2 * self.img_label.scale)
                    scaled_y2 = int(y2 * self.img_label.scale)
                    draw.line((scaled_x1, scaled_y1, scaled_x2, scaled_y2), fill="red", width=3)
            elif isinstance(item, tuple) and item[0] == 'text':  # 文字的历史记录
                _, scaled_x, scaled_y, text = item
                font = ImageFont.truetype("arial", size=int(28 * self.img_label.scale))
                draw.text((int(scaled_x * self.img_label.scale), int(scaled_y * self.img_label.scale)),
                          text, fill="red", font=font)
        self.img_label.image = ImageTk.PhotoImage(self.img_label.zoomed_image)
        self.img_label.config(image=self.img_label.image)

    def activate_window(self, event):
        self.app.exit_all_modes()

    def show_llm_settings(self):
        """显示LLM设置窗口"""
        from fastshot.settings import show_settings
        settings_window = show_settings(self.img_window, active_tab=2)  # 直接打开GenAI标签页

    def power_extract(self):
        """执行内容抽取"""
        # 保存当前图像到临时文件
        temp_path = "temp_extract.png"
        self.img_label.zoomed_image.save(temp_path)
        
        # 提取内容
        content = self.llm_extractor.extract_content(temp_path)
        
        # 删除临时文件
        try:
            os.remove(temp_path)
        except:
            pass
            
        # 显示结果
        if content:
            ExtractResultDialog(self.img_window, content)

    def hide(self):
        """Hides the image window."""
        if self.img_window.winfo_exists() and not self.is_hidden:
            self.img_window.withdraw()
            self.is_hidden = True
            print(f"Hiding window: {self.img_window.winfo_id()}")

    def show(self):
        """Shows the image window."""
        if self.img_window.winfo_exists() and self.is_hidden:
            self.img_window.deiconify()
            self.is_hidden = False
            print(f"Showing window: {self.img_window.winfo_id()}")

    def rotate_left(self):
        """逆时针旋转90度"""
        if self.img_label.original_image:
            # 旋转原始图像
            self.img_label.original_image = self.img_label.original_image.rotate(90, expand=True)
            
            # 重新计算缩放后的图像
            new_width = int(self.img_label.original_image.width * self.img_label.scale)
            new_height = int(self.img_label.original_image.height * self.img_label.scale)
            
            try:
                self.img_label.zoomed_image = self.img_label.original_image.resize((new_width, new_height), Image.LANCZOS)
                self.redraw_image()
                print("Image rotated 90° counter-clockwise")
            except Exception as e:
                print(f"Error during rotation: {e}")

    def rotate_right(self):
        """顺时针旋转90度"""
        if self.img_label.original_image:
            # 旋转原始图像
            self.img_label.original_image = self.img_label.original_image.rotate(-90, expand=True)
            
            # 重新计算缩放后的图像
            new_width = int(self.img_label.original_image.width * self.img_label.scale)
            new_height = int(self.img_label.original_image.height * self.img_label.scale)
            
            try:
                self.img_label.zoomed_image = self.img_label.original_image.resize((new_width, new_height), Image.LANCZOS)
                self.redraw_image()
                print("Image rotated 90° clockwise")
            except Exception as e:
                print(f"Error during rotation: {e}")
