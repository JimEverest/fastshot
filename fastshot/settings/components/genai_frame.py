import tkinter as tk
from tkinter import ttk

class GenAIFrame(ttk.Frame):
    def __init__(self, parent, settings_manager):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.create_widgets()
    
    def create_widgets(self):
        # 加载设置
        settings = self.settings_manager.get_section('PowerGenAI')
        
        # Base URL
        base_url_frame = ttk.Frame(self)
        base_url_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(base_url_frame, text="Base URL:").pack(side='left')
        self.base_url_var = tk.StringVar(value=settings.get('_base_url', ''))
        self.base_url_entry = ttk.Entry(base_url_frame, textvariable=self.base_url_var, width=40)
        self.base_url_entry.pack(side='left', padx=5, fill='x', expand=True)
        
        # API Key
        key_frame = ttk.Frame(self)
        key_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(key_frame, text="API Key:").pack(side='left')
        self.key_var = tk.StringVar(value=settings.get('key', ''))
        self.key_entry = ttk.Entry(key_frame, textvariable=self.key_var, width=40, show='*')
        self.key_entry.pack(side='left', padx=5, fill='x', expand=True)
        
        # Show/Hide Key button
        self.show_key_btn = ttk.Button(
            key_frame,
            text="Show",
            command=self.toggle_key_visibility,
            width=8
        )
        self.show_key_btn.pack(side='left', padx=5)
        
        # Model
        model_frame = ttk.Frame(self)
        model_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(model_frame, text="Model:").pack(side='left')
        self.model_var = tk.StringVar(value=settings.get('_model', ''))
        
        # 预定义的模型选项
        self.model_combo = ttk.Combobox(
            model_frame, 
            textvariable=self.model_var,
            values=[
                "google/gemini-2.0-pro-exp-02-05:free",
                "gpt-4o",
                # 可以添加更多模型选项
            ],
            width=37
        )
        self.model_combo.pack(side='left', padx=5, fill='x', expand=True)
        
        # 添加说明标签
        help_text = (
            "Note:\n"
            "1. Base URL example: https://openrouter.ai/api/v1\n"
            "2. API Key format: sk-or-v1-xxxxxx\n"
            "3. Select or input model name"
        )
        help_label = ttk.Label(
            self, 
            text=help_text,
            justify='left',
            foreground='gray'
        )
        help_label.pack(padx=10, pady=10, anchor='w')
    
    def toggle_key_visibility(self):
        """切换API Key的可见性"""
        if self.key_entry['show'] == '*':
            self.key_entry['show'] = ''
            self.show_key_btn['text'] = 'Hide'
        else:
            self.key_entry['show'] = '*'
            self.show_key_btn['text'] = 'Show'
    
    def get_settings(self):
        """获取当前设置"""
        return {
            '_base_url': self.base_url_var.get().strip(),
            'key': self.key_var.get().strip(),
            '_model': self.model_var.get().strip()
        } 