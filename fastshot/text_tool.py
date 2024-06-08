
import tkinter as tk
from PIL import ImageDraw, ImageFont

class TextTool:
    def __init__(self, image_window):
        self.image_window = image_window
        self.text_mode = False

    def enable_text_mode(self):
        if self.image_window.paint_tool:
            self.image_window.paint_tool.disable_paint_mode()
        self.text_mode = True
        img_label = self.image_window.img_label
        if img_label:
            img_label.bind('<Button-1>', self.add_text_entry)
        if self.image_window.root:
            self.image_window.root.bind_all('<Escape>', self.disable_text_mode)
            self.image_window.root.bind_all('<Control-z>', self.undo_last_text)
        img_label.config(cursor="xterm")
        self.image_window.set_text_tool(self)  # 设置当前 TextTool 实例为活动的文字工具

    def disable_text_mode(self, event=None):
        self.text_mode = False
        img_label = self.image_window.img_label
        if img_label:
            img_label.unbind('<Button-1>')
        if self.image_window.root:
            self.image_window.root.unbind_all('<Escape>')
            self.image_window.root.unbind_all('<Control-z>')
        img_label.config(cursor="arrow")

    def add_text_entry(self, event):
        if self.text_mode:
            x, y = event.x, event.y
            entry = tk.Entry(self.image_window.img_window, font=("Arial", 28), fg="red", bd=0, highlightthickness=0, insertbackground="red")
            entry.place(x=x, y=y)
            entry.bind('<Return>', lambda e: self.save_text(entry, x, y))
            entry.bind('<FocusOut>', lambda e: self.save_text(entry, x, y))
            entry.focus()
            self.text_entry = entry

    def save_text(self, entry, x, y):
        text = entry.get()
        entry.destroy()
        if text:
            scaled_x = x / self.image_window.img_label.scale
            scaled_y = y / self.image_window.img_label.scale
            self.image_window.draw_history.append(('text', scaled_x, scaled_y, text))
            self.image_window.redraw_image()

    def undo_last_text(self, event=None):
        if self.image_window.draw_history:
            for i in range(len(self.image_window.draw_history) - 1, -1, -1):
                if isinstance(self.image_window.draw_history[i], tuple) and self.image_window.draw_history[i][0] == 'text':
                    del self.image_window.draw_history[i]
                    break
            self.image_window.redraw_image()


