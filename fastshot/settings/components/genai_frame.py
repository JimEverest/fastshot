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
            ],
            width=37
        )
        self.model_combo.pack(side='left', padx=5, fill='x', expand=True)
        
        # 修改提示语配置部分，使用 Text 而不是 Entry
        prompt_frame = ttk.LabelFrame(self, text="Extraction Prompt")
        prompt_frame.pack(fill='x', padx=10, pady=5)
        
        # 创建文本框和滚动条
        self.prompt_text = tk.Text(prompt_frame, wrap=tk.WORD, height=6, width=40)
        prompt_scrollbar = ttk.Scrollbar(prompt_frame, orient=tk.VERTICAL, command=self.prompt_text.yview)
        self.prompt_text.configure(yscrollcommand=prompt_scrollbar.set)
        
        # 插入默认或保存的提示语
        default_prompt = (
            "**Task:** Analyze and describe the provided image screenshot in a structured "
            "Markdown format. The image may contain diagrams, charts, flows, system "
            "screenshots, tables, PPT slides, or similar visual representations of "
            "information. Your goal is to extract ALL relevant information and present "
            "it in a clear, concise, and organized manner."
        )
        current_prompt = self.settings_manager.get_section('PowerGenAI').get('extraction_prompt', default_prompt)
        self.prompt_text.insert('1.0', current_prompt)
        
        # 布局
        self.prompt_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        prompt_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
        
        # 添加说明标签
        help_text = (
            "Note:\n"
            "1. Base URL example: https://openrouter.ai/api/v1\n"
            "2. API Key format: sk-or-v1-xxxxxx\n"
            "3. Select or input model name\n"
            "4. Customize extraction prompt to guide the AI's analysis"
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
            '_model': self.model_var.get().strip(),
            'extraction_prompt': self.prompt_text.get('1.0', tk.END).strip()  # 从 Text 组件获取内容
        } 