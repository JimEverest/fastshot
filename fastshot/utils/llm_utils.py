import base64
import configparser
import os
from openai import OpenAI
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

class LLMExtractor:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = os.path.join(self.base_dir, 'config.ini')
        self.load_config()
        
    def load_config(self):
        """加载配置"""
        self.config.read(self.config_path)
        if 'PowerGenAI' not in self.config:
            messagebox.showerror("Error", "PowerGenAI configuration not found!")
            return False
        
        self._base_url = self.config['PowerGenAI'].get('_base_url', '')
        self.key = self.config['PowerGenAI'].get('key', '')
        self._model = self.config['PowerGenAI'].get('_model', '')
        
        if not all([self._base_url, self.key, self._model]):
            messagebox.showerror("Error", "Please configure LLM settings first!")
            return False
        return True
    
    def encode_image(self, image_path):
        """将图片转换为base64编码"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def extract_content(self, image_path):
        """提取图片内容"""
        if not self.load_config():
            return None
            
        try:
            client = OpenAI(
                base_url=self._base_url,
                api_key=self.key
            )
            
            base64_image = self.encode_image(image_path)
            
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "这张图片里有什么?请详细描述。"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                temperature=1
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to extract content: {str(e)}")
            return None

class ExtractResultDialog:
    def __init__(self, parent, content):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Content Extraction Result")
        self.create_widgets(content)
        
    def create_widgets(self, content):
        # 创建文本框和滚动条
        frame = ttk.Frame(self.dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        text_widget = tk.Text(frame, wrap=tk.WORD, width=60, height=20)
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        # 插入内容
        text_widget.insert(tk.END, content)
        text_widget.config(state=tk.DISABLED)  # 设为只读
        
        # 布局
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 底部按钮
        btn_frame = ttk.Frame(self.dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(btn_frame, text="Copy", command=lambda: self.copy_to_clipboard(content)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
        
    def copy_to_clipboard(self, content):
        self.dialog.clipboard_clear()
        self.dialog.clipboard_append(content)
        messagebox.showinfo("Success", "Content copied to clipboard!") 