import tkinter as tk
from tkinter import ttk
from tkinter import colorchooser

class ScreenPenFrame(ttk.Frame):
    def __init__(self, parent, settings_manager):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.settings = {}
        self.create_widgets()
    
    def create_widgets(self):
        # 加载设置
        settings = self.settings_manager.get_section('ScreenPen')
        
        # 启用开关
        enable_frame = ttk.Frame(self)
        enable_frame.pack(fill='x', padx=10, pady=5)
        
        self.enable_var = tk.BooleanVar(value=settings.get('enable_screenpen') == 'True')
        enable_cb = ttk.Checkbutton(
            enable_frame, 
            text="Enable Screen Pen",
            variable=self.enable_var
        )
        enable_cb.pack(side='left')
        
        # 画笔颜色
        color_frame = ttk.Frame(self)
        color_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(color_frame, text="Pen Color:").pack(side='left')
        self.color_btn = ttk.Button(
            color_frame,
            text="Choose Color",
            command=self.choose_color
        )
        self.color_btn.pack(side='left', padx=5)
        
        self.color_var = tk.StringVar(value=settings.get('pen_color', 'red'))
        self.color_preview = tk.Canvas(color_frame, width=20, height=20)
        self.color_preview.pack(side='left')
        self.update_color_preview()
        
        # 画笔宽度
        width_frame = ttk.Frame(self)
        width_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(width_frame, text="Pen Width:").pack(side='left')
        self.width_var = tk.StringVar(value=settings.get('pen_width', '3'))
        width_spinbox = ttk.Spinbox(
            width_frame,
            from_=1,
            to=20,
            textvariable=self.width_var,
            width=5
        )
        width_spinbox.pack(side='left', padx=5)
    
    def choose_color(self):
        color = colorchooser.askcolor(color=self.color_var.get())[1]
        if color:
            self.color_var.set(color)
            self.update_color_preview()
    
    def update_color_preview(self):
        self.color_preview.delete('all')
        self.color_preview.create_rectangle(
            0, 0, 20, 20,
            fill=self.color_var.get(),
            outline=''
        )
    
    def get_settings(self):
        """获取当前设置"""
        return {
            'enable_screenpen': str(self.enable_var.get()),
            'pen_color': self.color_var.get(),
            'pen_width': self.width_var.get()
        } 