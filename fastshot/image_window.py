import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
import io
import win32clipboard
from pynput import keyboard
from .paint_tool import PaintTool
from .text_tool import TextTool

class ImageWindow:
    def __init__(self, app, img):
        self.app = app
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

        hotkey_paint = keyboard.HotKey(keyboard.HotKey.parse('<ctrl>+p'), on_activate_paint)
        hotkey_text = keyboard.HotKey(keyboard.HotKey.parse('<ctrl>+t'), on_activate_text)

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
        if not self.paint_tool.painting and not self.text_tool.text_mode:
            x = self.img_window.winfo_x() + event.x - self.img_window._drag_data["x"]
            y = self.img_window.winfo_y() + event.y - self.img_window._drag_data["y"]
            self.img_window.geometry(f"+{x}+{y}")

    def show_context_menu(self, event):
        menu = tk.Menu(self.img_window, tearoff=0)

        # 使用 Unicode 字符作为图标
        icons = {
            "Close": "❌",
            "Save As...": "💾",
            "Paint": "🖌️",
            "Undo": "↩️",
            "Exit Edit": "🚪",
            "Copy": "📋",
            "Text": "🔤",
            "OCR": "🔍"
        }

        commands = {
            "Close": self.close,
            "Save As...": self.save_as,
            "Paint": self.paint,
            "Undo": self.undo,
            "Exit Edit": self.exit_edit_mode,
            "Copy": self.copy,
            "Text": self.text,
            "OCR": self.ocr
        }

        for label, icon in icons.items():
            menu.add_command(label=f"{icon} {label}", command=commands[label])

        menu.post(event.x_root, event.y_root)

    def close(self):
        self.img_window.destroy()
        self.app.windows.remove(self)

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
        scale_factor = 1.1 if event.delta > 0 else 0.9
        self.img_label.scale *= scale_factor
        new_width = int(self.img_label.original_image.width * self.img_label.scale)
        new_height = int(self.img_label.original_image.height * self.img_label.scale)
        self.img_label.zoomed_image = self.img_label.original_image.resize((new_width, new_height), Image.LANCZOS)
        self.redraw_image()

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
