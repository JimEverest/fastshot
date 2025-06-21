# plugin_hello_world.py
import tkinter as tk
from tkinter import messagebox
import os
from utils.hyder import FileHyder
import win32clipboard

def copy(text):
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()
    print(f"已复制到剪贴板: {text}")

def run(app_context):
    """The main function that gets called when the plugin is activated."""
    print("Hello, htder!")
    hider = FileHyder()
    encoded_path = hider.encode(
        file_path=None,        # 如果为 None，将从剪贴板获取
        img_path= os.path.join(os.path.dirname(__file__), '../resources', "tk_color_chart.png"),
        key="qwer1234",        # 加密密钥
        output_dir="output"    # 输出目录，默认为当前目录
    )
    if encoded_path:
        print(f"编码完成，输出文件路径: {encoded_path}")
        copy(encoded_path)
    return encoded_path


def get_plugin_info():
    """Returns metadata about the plugin."""
    return {
        'name': 'Hyder Plugin',
        'id': 'plugin_hyder',
        'description': 'A sample plugin that shows a Hello plgin message.',
        'author': 'Jim',
        'version': '1.0',
        'default_shortcut': 'alt',
        'press_times': 4,
        'enabled': True
    }
