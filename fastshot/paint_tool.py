
import tkinter as tk
from PIL import ImageDraw

class PaintTool:
    def __init__(self, image_window):
        self.image_window = image_window
        self.painting = False
        self.last_x = self.last_y = None

    def enable_paint_mode(self):
        if self.image_window.text_tool:
            self.image_window.text_tool.disable_text_mode()
        self.painting = True
        img_label = self.image_window.img_label
        if img_label:
            img_label.bind('<B1-Motion>', self.paint)
            img_label.bind('<ButtonPress-1>', self.on_mouse_down)
        if self.image_window.root:
            self.image_window.root.bind_all('<Escape>', self.disable_paint_mode)
            self.image_window.root.bind_all('<Control-z>', self.undo_last_draw)
        img_label.config(cursor="pencil")
        self.image_window.set_paint_tool(self)  # 设置当前 PaintTool 实例为活动的绘图工具

    def disable_paint_mode(self, event=None):
        self.painting = False
        img_label = self.image_window.img_label
        if img_label:
            img_label.unbind('<B1-Motion>')
            img_label.unbind('<ButtonPress-1>')
        if self.image_window.root:
            self.image_window.root.unbind_all('<Escape>')
            self.image_window.root.unbind_all('<Control-z>')
        img_label.config(cursor="arrow")

    def on_mouse_down(self, event):
        self.last_x, self.last_y = event.x, event.y
        # 检查最后一项是否为列表，如果不是则添加一个新列表
        if not self.image_window.draw_history or not isinstance(self.image_window.draw_history[-1], list):
            self.image_window.draw_history.append([])

    def paint(self, event):
        if self.painting:
            img_label = self.image_window.img_label
            x, y = event.x, event.y
            scaled_last_x = self.last_x / img_label.scale
            scaled_last_y = self.last_y / img_label.scale
            scaled_x = x / img_label.scale
            scaled_y = y / img_label.scale
            self.image_window.draw_history[-1].append((scaled_last_x, scaled_last_y, scaled_x, scaled_y))
            self.last_x, self.last_y = x, y
            self.image_window.redraw_image()

    def undo_last_draw(self, event=None):
        if self.image_window.draw_history:
            self.image_window.draw_history.pop()
            self.image_window.redraw_image()

