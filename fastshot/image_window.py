import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
import io
import win32clipboard
from pynput import keyboard

from .paint_tool import PaintTool
from .text_tool import TextTool
from .ask_dialog import AskDialog  # 导入 AskDialog 类

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
        menu = tk.Menu(self.img_window, tearoff=0)

        # 使用 Unicode 字符作为图标
        icons = {
            "Copy": "📋",
            "Close": "❌",
            "Save As...": "💾",
            "Paint": "🎨",
            "Undo": "↺",
            "Exit Edit": "🚪",
            "Text": "🔤",
            "OCR": "🧾",
            "Ask": "💬"  # 新增 Ask 选项
        }

        commands = {
            "Copy": self.copy,
            "Close": self.close,
            "Save As...": self.save_as,
            "Paint": self.paint,
            "Undo": self.undo,
            "Exit Edit": self.exit_edit_mode,
            "Text": self.text,
            "OCR": self.ocr,
            "Ask": self.open_ask_dialog  # 新增 Ask 命令
        }

        for label, icon in icons.items():
            menu.add_command(label=f"{icon} {label}", command=commands[label])

        menu.post(event.x_root, event.y_root)

    def close(self):
        if self.ask_dialog and self.ask_dialog.dialog_window and self.ask_dialog.dialog_window.winfo_exists():
            self.ask_dialog.clean_and_close()
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

    def disable_interactions(self):
        # 禁用截图的移动和缩放功能
        self.img_window.unbind('<ButtonPress-1>')
        self.img_window.unbind('<B1-Motion>')
        self.img_window.unbind('<MouseWheel>')

    def enable_interactions(self):
        # 恢复截图的移动和缩放功能
        self.img_window.bind('<ButtonPress-1>', self.start_move)
        self.img_window.bind('<B1-Motion>', self.do_move)
        self.img_window.bind('<MouseWheel>', self.zoom)





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
