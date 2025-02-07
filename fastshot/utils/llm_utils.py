import base64
import configparser
import os
from openai import OpenAI
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
import httpx

class LLMExtractor:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = os.path.join(self.base_dir, 'config.ini')
        # 获取代理设置
        self.proxy_url = os.environ.get("OPENAI_PROXY_URL", "")
    
    def load_config(self):
        """动态加载配置"""
        self.config.read(self.config_path)
        if 'PowerGenAI' not in self.config:
            messagebox.showerror("Error", "PowerGenAI configuration not found!")
            return None, None, None, None
        
        _base_url = self.config['PowerGenAI'].get('_base_url', '')
        key = self.config['PowerGenAI'].get('key', '')
        _model = self.config['PowerGenAI'].get('_model', '')
        extraction_prompt = self.config['PowerGenAI'].get('extraction_prompt', 'describe the image')
        
        if not all([_base_url, key, _model]):
            messagebox.showerror("Error", "Please configure LLM settings first!")
            return None, None, None, None
        return _base_url, key, _model, extraction_prompt
    
    def encode_image(self, image_path):
        """将图片转换为base64编码"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def create_client(self, base_url, key):
        """创建 OpenAI 客户端"""
        kwargs = {
            'base_url': base_url,
            'api_key': key
        }
        
        if self.proxy_url:
            print("_proxy_url: ", self.proxy_url)
            kwargs['http_client'] = httpx.Client(
                proxies={
                    'http://': self.proxy_url,
                    'https://': self.proxy_url
                },
                verify=False  # Ignore SSL certificate verification
            )
        return OpenAI(**kwargs)
    
    def extract_content(self, image_path):
        """提取图片内容"""
        # 每次执行时动态加载配置
        base_url, key, model, prompt = self.load_config()
        if None in (base_url, key, model, prompt):
            return None
            
        try:
            # 使用最新的配置创建客户端
            client = self.create_client(base_url, key)
            base64_image = self.encode_image(image_path)
            
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},  # 使用配置的提示语
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