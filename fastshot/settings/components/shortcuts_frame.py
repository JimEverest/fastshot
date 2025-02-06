import tkinter as tk
from tkinter import ttk
from ..utils.hotkey_capture import HotkeyCapture

class ShortcutsFrame(ttk.Frame):
    def __init__(self, parent, settings_manager):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.hotkey_capture = HotkeyCapture()
        self.shortcuts = {}
        self.create_widgets()
    
    def create_widgets(self):
        # 创建滚动框架
        canvas = tk.Canvas(self)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # 加载快捷键设置
        shortcuts = self.settings_manager.get_section('Shortcuts')
        for key, value in shortcuts.items():
            self.create_shortcut_row(key, value)

        # 布局
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def create_shortcut_row(self, key, value):
        frame = ttk.Frame(self.scrollable_frame)
        frame.pack(fill='x', padx=5, pady=2)
        
        # 标签
        label = ttk.Label(frame, text=key.replace('_', ' ').title())
        label.pack(side='left', padx=5)
        
        # 快捷键输入框
        entry = ttk.Entry(frame, width=20)
        entry.insert(0, value)
        entry.pack(side='left', padx=5)
        self.shortcuts[key] = entry
        
        # 捕获按钮
        capture_btn = ttk.Button(
            frame, 
            text="Capture",
            command=lambda k=key: self.capture_hotkey(k)
        )
        capture_btn.pack(side='left', padx=5)
    
    def capture_hotkey(self, key):
        """捕获快捷键"""
        hotkey = self.hotkey_capture.capture()
        if hotkey:
            self.shortcuts[key].delete(0, tk.END)
            self.shortcuts[key].insert(0, hotkey)
    
    def get_settings(self):
        """获取当前设置"""
        return {
            key: entry.get() 
            for key, entry in self.shortcuts.items()
        } 