# plugin_hello_world.py

import tkinter as tk
from tkinter import messagebox
import os
from utils.minio_helper import S3Client
from datetime import datetime
import win32clipboard
from win32con import CF_HDROP, CF_UNICODETEXT
import zipfile
import re

def copy(text):
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()
    print(f"已复制到剪贴板: {text}")

def normalize_path(path):
    """
    将路径中的反斜杠和多余的正斜杠规范化为单一的正斜杠。
    例如:
        "C:\\Users\\Admin\\file.txt" -> "C:/Users/Admin/file.txt"
        "C://Users//Admin//file.txt" -> "C:/Users/Admin/file.txt"
    """
    path = path.replace('\\', '/')
    path = re.sub(r'/+', '/', path)
    return path

def get_clipboard_file_path():
    """
    从剪贴板中获取文件路径或字符串。
    如果剪贴板中是文件/文件夹，返回路径字符串列表。
    如果剪贴板中是字符串，返回字符串。
    如果剪贴板为空或不支持的格式，返回 None。
    """
    try:
        win32clipboard.OpenClipboard()
        if win32clipboard.IsClipboardFormatAvailable(CF_HDROP):
            files = win32clipboard.GetClipboardData(CF_HDROP)
            normalized_files = [normalize_path(file) for file in files]
            return normalized_files
        elif win32clipboard.IsClipboardFormatAvailable(CF_UNICODETEXT):
            text = win32clipboard.GetClipboardData(CF_UNICODETEXT).strip()
            if not text:
                return None
            normalized_text = normalize_path(text)
            # 判断是否为存在的路径
            if os.path.exists(normalized_text):
                return normalized_text
            else:
                return text
        else:
            return None
    except Exception as e:
        print(f"从剪贴板获取数据时发生错误: {e}")
        return None
    finally:
        win32clipboard.CloseClipboard()


def run(app_context):
    """The main function that gets called when the plugin is activated."""
    # Display a Hello World message box
    # root = tk.Tk()
    # root.withdraw()
    # messagebox.showinfo("Hello Plugin", "Hello, World!")
    # root.destroy()

    local_file=get_clipboard_file_path()[0]

    # 确保环境变量已设置

    endpoint= "20.187.52.241:9000"
    access_key = 'IgsRutWhylZ8R2pUR3e8'
    secret_key = 'HpW0kcFUjE37lzw2YXaX2g7UVSHCRkbLBQWVq8py'
    bucket_name = 'pub-bucket'

    secure = False

    # 初始化S3Client，不需要传递参数，因为它会从环境变量中读取
    s3_client = S3Client(endpoint=endpoint, access_key=access_key, secret_key=secret_key, bucket_name=bucket_name, secure=secure)


    # 上传文件
    # get orighianl extention name:
    ext = os.path.splitext(local_file)[1]
    # timestamp in YYMMDDHHMMSS format
    timestamp = datetime.now().strftime('%y%m%d%H%M%S')+ext
    object_name = timestamp  # 或者使用None以自动获取文件名
    s3_client.upload_file(local_file, object_name)

    public_url = s3_client.get_direct_url(object_name, days=-1)
    print(f"公开URL：\n{public_url}")
    copy(public_url)




def get_plugin_info():
    """Returns metadata about the plugin."""
    return {
        'name': 'Hello World Plugin',
        'id': 'plugin_mini',
        'description': 'A sample plugin that shows a Hello World message.',
        'author': 'Jim',
        'version': '1.0',
        'default_shortcut': '\\',
        'press_times': 6,
        'enabled': True
    }
