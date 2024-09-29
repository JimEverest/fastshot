# fastshot/ask_dialog.py

import tkinter as tk
from tkinter import scrolledtext
from PIL import ImageTk, Image
import threading
import time
import random
import os
import io
import base64
import json

class AskDialog:
    def __init__(self, image_window):
        self.image_window = image_window
        self.is_minimized = False
        self.dialog_icon = None
        self.resizing = False  # 标记是否正在调整大小
        self.resize_dir = None  # 调整大小的方向

        # 创建顶层窗口
        self.dialog_window = tk.Toplevel(image_window.img_window)
        self.dialog_window.title("Ask")
        self.dialog_window.geometry("400x600")
        self.dialog_window.minsize(300, 400)
        self.dialog_window.attributes('-topmost', True)

        # 隐藏系统窗口装饰
        self.dialog_window.overrideredirect(True)

        # 自定义标题栏
        self.create_title_bar()

        # 禁用截图的移动和缩放功能
        self.image_window.disable_interactions()
        self.image_window.is_dialog_open = True

        # 加载用户和 AI 头像
        self.user_icon = self.load_icon("user_icon.png")
        self.ai_icon = self.load_icon("ai_icon.png")

        # 创建主框架，包含聊天显示、输入框和按钮
        self.create_main_frame()

        # 加载并显示截图缩略图
        self.show_thumbnail()

        # 保存对话历史
        self.chat_history = []
        # 初始化 messages 列表
        self.messages = [
            {"role": "system", "content": "You are a helpful assistant."}
        ]
        self.is_first_query = True  # 标记是否是第一次提问

        # 绑定窗口事件
        self.dialog_window.bind('<Motion>', self.change_cursor)
        self.dialog_window.bind('<ButtonRelease-1>', self.on_release)
        self.dialog_window.bind('<Configure>', self.on_configure)

        # 处理窗口关闭事件
        self.dialog_window.protocol("WM_DELETE_WINDOW", self.on_window_close)


    def create_title_bar(self):
        self.title_bar = tk.Frame(self.dialog_window, bg='#2e2e2e', relief='raised', bd=0)
        self.title_bar.pack(fill=tk.X)

        self.title_label = tk.Label(self.title_bar, text='Ask', bg='#2e2e2e', fg='white')
        self.title_label.pack(side=tk.LEFT, padx=10)

        # 窗口控制按钮
        self.btn_close = tk.Button(self.title_bar, text='X', command=self.clean_and_close, bg='#2e2e2e', fg='white', bd=0)
        self.btn_close.pack(side=tk.RIGHT, padx=5)

        self.btn_minimize = tk.Button(self.title_bar, text='-', command=self.minimize_dialog, bg='#2e2e2e', fg='white', bd=0)
        self.btn_minimize.pack(side=tk.RIGHT)

        # 绑定拖拽事件
        self.title_bar.bind('<ButtonPress-1>', self.start_move)
        self.title_bar.bind('<B1-Motion>', self.do_move)
        self.title_label.bind('<ButtonPress-1>', self.start_move)
        self.title_label.bind('<B1-Motion>', self.do_move)

    def create_main_frame(self):
        # 创建主框架
        self.main_frame = tk.Frame(self.dialog_window)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # 聊天显示区域
        self.chat_display = scrolledtext.ScrolledText(self.main_frame, wrap=tk.WORD)
        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.pack(fill=tk.BOTH, expand=True)

        # 输入框和按钮框架
        self.input_frame = tk.Frame(self.main_frame)
        self.input_frame.pack(fill=tk.X)

        # 输入框
        self.user_entry = tk.Text(self.input_frame, height=6)
        self.user_entry.pack(fill=tk.BOTH, side=tk.LEFT, expand=True, padx=5, pady=5)
        self.user_entry.bind("<Shift-Return>", self.on_submit_click)

        # 按钮框架
        self.button_frame = tk.Frame(self.main_frame)
        self.button_frame.pack(fill=tk.X)

        self.submit_button = tk.Button(self.button_frame, text="Submit", command=self.on_submit_click)
        self.submit_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.cancel_button = tk.Button(self.button_frame, text="Cancel", command=self.minimize_dialog)
        self.cancel_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.clean_button = tk.Button(self.button_frame, text="Clean", command=self.clean_and_close)
        self.clean_button.pack(side=tk.LEFT, padx=5, pady=5)

    def show_thumbnail(self):
        # 加载并缩放截图
        original_image = self.image_window.img_label.zoomed_image
        max_size = 300  # 最长边不超过 300 像素

        # 计算缩放比例
        w, h = original_image.size
        if w > h:
            scale_factor = max_size / float(w)
        else:
            scale_factor = max_size / float(h)

        new_w = int(w * scale_factor)
        new_h = int(h * scale_factor)

        thumbnail_image = original_image.resize((new_w, new_h), Image.LANCZOS)
        self.thumbnail_photo = ImageTk.PhotoImage(thumbnail_image)

        # 创建用于显示缩略图的 Frame
        self.thumbnail_frame = tk.Frame(self.main_frame)
        self.thumbnail_frame.pack(side=tk.TOP, pady=5)
        self.thumbnail_frame.config(width=300, height=300)
        self.thumbnail_frame.pack_propagate(False)  # 防止 Frame 随内部组件大小改变

        # 创建用于显示缩略图的 Label
        self.thumbnail_label = tk.Label(self.thumbnail_frame, image=self.thumbnail_photo)
        self.thumbnail_label.place(relx=0.5, rely=0.5, anchor='center')  # 居中显示

    def load_icon(self, filename):
        icon_path = os.path.join(os.path.dirname(__file__), 'resources', filename)
        if os.path.exists(icon_path):
            icon = Image.open(icon_path)
            icon = icon.resize((30, 30), Image.LANCZOS)
            return ImageTk.PhotoImage(icon)
        else:
            # 如果找不到图标，返回 None
            return None

    def on_window_close(self):
        self.clean_and_close()

    def on_submit_click(self, event=None):
        user_input = self.user_entry.get("1.0", tk.END).strip()
        if user_input:
            self.user_entry.delete("1.0", tk.END)
            self.append_message("You", user_input, self.user_icon)

            # 将用户的提问添加到 messages 列表
            if self.is_first_query:
                # 第一次提问，包含文本和图片
                current_image = self.image_window.img_label.zoomed_image.copy()
                buffered = io.BytesIO()
                current_image.save(buffered, format="JPEG")
                img_str = base64.b64encode(buffered.getvalue()).decode('ascii')
                user_content = [
                    {"type": "text", "text": user_input},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_str}"}}
                ]
                self.is_first_query = False
            else:
                # 后续提问，仅包含文本
                user_content = user_input

            self.messages.append({
                "role": "user",
                "content": user_content
            })

            # 调用 ask_dummy 函数，传递 messages 列表
            threading.Thread(target=self.ask_dummy).start()
        return 'break'

    def append_message(self, sender, message, icon):
        self.chat_display.config(state=tk.NORMAL)
        if not hasattr(self.chat_display, 'image_list'):
            self.chat_display.image_list = []
        if icon:
            self.chat_display.image_list.append(icon)
            self.chat_display.window_create(tk.END, window=tk.Label(self.chat_display, image=icon))
            self.chat_display.insert(tk.END, f" {sender}:\n{message}\n\n")
        else:
            self.chat_display.insert(tk.END, f"{sender}:\n{message}\n\n")
        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)

    def ask_dummy(self):
        # 模拟发送 messages 列表到 OpenAI GPT-4V 模型
        # 弹出一个窗口，显示 messages 列表的 JSON 格式
        self.dialog_window.after(0, self.show_messages_json)

        # 模拟长时间运行的任务
        time.sleep(2)

        # 模拟生成的回答
        answer_text = "This is a simulated response from GPT-4V."

        # 将 AI 的回答添加到 messages 列表
        self.messages.append({
            "role": "assistant",
            "content": answer_text
        })

        # 在主线程中更新 UI，显示 AI 的回答
        self.dialog_window.after(0, self.append_message, "AI Assistant", answer_text, self.ai_icon)

        # 显示接收到的图片（测试/调试用途）
        if self.is_first_query:
            # 如果是第一次提问，显示图片
            current_image = self.image_window.img_label.zoomed_image.copy()
            self.dialog_window.after(0, self.show_received_image, current_image)


    def show_messages_json(self):
        # 创建一个新的窗口，显示 messages 列表的 JSON 格式
        json_window = tk.Toplevel(self.dialog_window)
        json_window.title("Messages JSON")
        json_window.attributes('-topmost', True)
        json_window.geometry("600x400")

        json_text = json.dumps(self.messages, indent=4)
        text_widget = scrolledtext.ScrolledText(json_window, wrap=tk.WORD)
        text_widget.insert(tk.END, json_text)
        text_widget.config(state=tk.DISABLED)
        text_widget.pack(fill=tk.BOTH, expand=True)

    def show_received_image(self, image):
        img_window = tk.Toplevel(self.dialog_window)
        img_window.title("Received Image")
        img_window.attributes('-topmost', True)
        # 调整图像大小以适应窗口
        img_width, img_height = image.size
        max_size = (800, 600)
        if img_width > max_size[0] or img_height > max_size[1]:
            scale = min(max_size[0]/img_width, max_size[1]/img_height)
            new_size = (int(img_width * scale), int(img_height * scale))
            display_image = image.resize(new_size, Image.LANCZOS)
        else:
            display_image = image.copy()
        photo = ImageTk.PhotoImage(display_image)
        img_label = tk.Label(img_window, image=photo)
        img_label.image = photo  # 保持引用
        img_label.pack()

    def minimize_dialog(self):
        self.dialog_window.withdraw()
        self.is_minimized = True
        self.create_dialog_icon()
        # 启用截图的移动和缩放功能
        self.image_window.enable_interactions()
        self.image_window.is_dialog_open = False  # 更新状态

    def maximize_dialog(self, event=None):
        self.dialog_window.deiconify()
        self.is_minimized = False
        if self.dialog_icon:
            self.dialog_icon.destroy()
            self.dialog_icon = None
        # 禁用截图的移动和缩放功能
        self.image_window.disable_interactions()
        self.image_window.is_dialog_open = True  # 更新状态

    def clean_and_close(self):
        self.chat_history.clear()
        self.messages.clear()
        self.messages = [
            {"role": "system", "content": "You are a helpful assistant."}
        ]
        self.is_first_query = True

        if self.dialog_window:
            self.dialog_window.destroy()
            self.dialog_window = None
        if self.dialog_icon:
            self.dialog_icon.destroy()
            self.dialog_icon = None
        # 恢复截图的移动和缩放功能
        self.image_window.enable_interactions()
        self.image_window.ask_dialog = None  # 重置引用
        self.image_window.is_dialog_open = False  # 更新状态

    def create_dialog_icon(self):
        if self.dialog_icon:
            self.dialog_icon.destroy()

        self.dialog_icon = tk.Label(self.image_window.img_window, text="💬", cursor="hand2")
        self.dialog_icon.place(relx=1.0, rely=0.0, anchor='ne', x=-10, y=10)
        self.dialog_icon.bind("<Button-1>", self.maximize_dialog)

    def update_dialog_icon_position(self):
        if self.dialog_icon:
            self.dialog_icon.place(relx=1.0, rely=0.0, anchor='ne', x=-10, y=10)

    # 实现窗口拖拽
    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.dialog_window.winfo_x() + deltax
        y = self.dialog_window.winfo_y() + deltay
        self.dialog_window.geometry(f"+{x}+{y}")

    # 改变光标以实现窗口缩放
    def change_cursor(self, event):
        width = self.dialog_window.winfo_width()
        height = self.dialog_window.winfo_height()
        x = event.x
        y = event.y
        border_width = 5  # 调整边框的宽度

        # 初始化
        self.resize_dir = None

        if x < border_width and y < border_width:
            self.dialog_window.config(cursor='top_left_corner')
            self.resize_dir = 'nw'
        elif x > width - border_width and y < border_width:
            self.dialog_window.config(cursor='top_right_corner')
            self.resize_dir = 'ne'
        elif x < border_width and y > height - border_width:
            self.dialog_window.config(cursor='bottom_left_corner')
            self.resize_dir = 'sw'
        elif x > width - border_width and y > height - border_width:
            self.dialog_window.config(cursor='bottom_right_corner')
            self.resize_dir = 'se'
        elif x < border_width:
            self.dialog_window.config(cursor='left_side')
            self.resize_dir = 'w'
        elif x > width - border_width:
            self.dialog_window.config(cursor='right_side')
            self.resize_dir = 'e'
        elif y < border_width:
            self.dialog_window.config(cursor='top_side')
            self.resize_dir = 'n'
        elif y > height - border_width:
            self.dialog_window.config(cursor='bottom_side')
            self.resize_dir = 's'
        else:
            self.dialog_window.config(cursor='')
            self.resize_dir = None

        if self.resize_dir:
            self.dialog_window.bind('<ButtonPress-1>', self.start_resize)
            self.dialog_window.bind('<B1-Motion>', self.do_resize)
        else:
            # 防止与移动窗口事件冲突
            self.dialog_window.unbind('<ButtonPress-1>')
            self.dialog_window.unbind('<B1-Motion>')
            self.title_bar.bind('<ButtonPress-1>', self.start_move)
            self.title_bar.bind('<B1-Motion>', self.do_move)
            self.title_label.bind('<ButtonPress-1>', self.start_move)
            self.title_label.bind('<B1-Motion>', self.do_move)

    # 实现窗口缩放
    def start_resize(self, event):
        self.resizing = True
        self.lastX = event.x_root
        self.lastY = event.y_root
        self.start_width = self.dialog_window.winfo_width()
        self.start_height = self.dialog_window.winfo_height()
        self.start_x = self.dialog_window.winfo_x()
        self.start_y = self.dialog_window.winfo_y()

    def do_resize(self, event):
        if self.resizing and self.resize_dir:
            deltaX = event.x_root - self.lastX
            deltaY = event.y_root - self.lastY
            min_width = 300
            min_height = 400

            new_width = self.start_width
            new_height = self.start_height
            new_x = self.start_x
            new_y = self.start_y

            if 'e' in self.resize_dir:
                new_width = max(self.start_width + deltaX, min_width)
            if 's' in self.resize_dir:
                new_height = max(self.start_height + deltaY, min_height)
            if 'w' in self.resize_dir:
                new_width = max(self.start_width - deltaX, min_width)
                new_x = self.start_x + deltaX
            if 'n' in self.resize_dir:
                new_height = max(self.start_height - deltaY, min_height)
                new_y = self.start_y + deltaY

            self.dialog_window.geometry(f"{int(new_width)}x{int(new_height)}+{int(new_x)}+{int(new_y)}")

    def on_release(self, event):
        self.resizing = False
        self.dialog_window.config(cursor='')

    def on_configure(self, event):
        # 在窗口大小变化后，更新对话图标位置
        self.update_dialog_icon_position()