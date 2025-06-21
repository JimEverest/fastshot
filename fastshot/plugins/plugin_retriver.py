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
    # Display a Hello World message box
    print("Hello, retriver!")
    hider = FileHyder()
    decoded_folder = hider.decode(
        img_path=None,         # 如果为 None，将从剪贴板获取
        key="qwer1234",        # 解密密钥
        output_dir="decoded"   # 输出目录，默认为当前目录
    )
    if decoded_folder:
        print(f"解码完成，输出文件夹路径: {decoded_folder}")
        copy(decoded_folder)
    return decoded_folder
    # show_message_and_copy(decoded_folder)



def get_plugin_info():
    """Returns metadata about the plugin."""
    return {
        'name': 'plugin_retriver',
        'id': 'plugin_retriver',
        'description': 'A sample plugin that shows a Hello plgin message.',
        'author': 'Jim',
        'version': '1.0',
        'default_shortcut': 'cmd',
        'press_times': 4,
        'enabled': True
    }
