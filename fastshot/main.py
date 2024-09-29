import os
if os.name == 'nt':
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
    except Exception as e:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception as e:
            print(f"无法设置DPI感知: {e}")

import tkinter as tk
from pynput import keyboard
from screeninfo import get_monitors
import ctypes
import importlib
import os
import configparser
import urllib.request
import zipfile
import shutil

from fastshot.snipping_tool import SnippingTool
from fastshot.image_window import ImageWindow
from fastshot.screen_pen import ScreenPen  # 导入 ScreenPen
from fastshot.window_control import HotkeyListener, load_config







class SnipasteApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.monitors = get_monitors()
        self.snipping_tool = SnippingTool(self.root, self.monitors, self.on_screenshot)
        self.windows = []
        self.plugins = {}
        self.config = self.load_config()
        self.print_config_info()
        self.check_and_download_models()
        self.load_plugins()
        self.setup_hotkey_listener()
        listener = HotkeyListener(self.config)
        listener.start()


        # 初始化 ScreenPen
        enable_screenpen = self.config['ScreenPen'].getboolean('enable_screenpen', True)
        if enable_screenpen:
            self.screen_pen = ScreenPen(self.root, self.config)
            self.screen_pen.start_keyboard_listener()
        else:
            self.screen_pen = None

    def load_config(self):
        config = configparser.ConfigParser()
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
        if not os.path.exists(config_path):
            # 创建默认的配置文件
            config['Paths'] = {
                'download_url': 'https://raw.githubusercontent.com/JimEverest/ppocr_v4_models/main/.paddleocr.zip'
            }
            config['Shortcuts'] = {
                'hotkey_snip': '<shift>+a+s',
                'hotkey_paint': '<ctrl>+p',
                'hotkey_text': '<ctrl>+t',
                'hotkey_screenpen_toggle': '<ctrl>+x+c',
                'hotkey_undo': '<ctrl>+z',
                'hotkey_redo': '<ctrl>+y',
                'hotkey_screenpen_exit': '<esc>',
                'hotkey_screenpen_clear_hide': '<ctrl>+<esc>'
            }
            config['ScreenPen'] = {
                'enable_screenpen': 'True',
                'pen_color': 'red',
                'pen_width': '3',
                'smooth_factor': '3'
            }
            with open(config_path, 'w', encoding='utf-8') as configfile:
                config.write(configfile)
        else:
            config.read(config_path, encoding='utf-8')
        self.config_path = config_path
        return config

    def print_config_info(self):
        print(f"配置文件路径: {self.config_path}")
        print("快捷键设置:")
        shortcut_descriptions = {
            'hotkey_snip': '启动截图',
            'hotkey_paint': '启用画笔模式',
            'hotkey_text': '启用文字模式',
            'hotkey_screenpen_toggle': '切换屏幕画笔模式',
            'hotkey_undo': '撤销上一步',
            'hotkey_redo': '重做上一步',
            'hotkey_screenpen_exit': '退出屏幕画笔模式',
            'hotkey_screenpen_clear_hide': '清除画笔并隐藏'
        }
        for key, desc in shortcut_descriptions.items():
            value = self.config['Shortcuts'].get(key, '')
            print(f"{desc}: {value}")

    # def check_and_download_models(self):
    #     home_dir = os.path.expanduser('~')  #C:\Users\xxxxxxx/
    #     paddleocr_dir = os.path.join(home_dir, '.paddleocr', 'whl')#C:\Users\xxxxxxx/.paddleocr/whl/
    #     model_dirs = [
    #         os.path.join(paddleocr_dir, 'det', 'ch', 'ch_PP-OCRv4_det_infer'),#C:\Users\xxxxxxx/.paddleocr/whl/det/ch/ch_PP-OCRv4_det_infer/
    #         os.path.join(paddleocr_dir, 'rec', 'ch', 'ch_PP-OCRv4_rec_infer'),#C:\Users\xxxxxxx/.paddleocr/whl/rec/ch/ch_PP-OCRv4_rec_infer/
    #         os.path.join(paddleocr_dir, 'cls', 'ch_ppocr_mobile_v2.0_cls_infer')#C:\Users\xxxxxxx/.paddleocr/whl/cls/ch_ppocr_mobile_v2.0_cls_infer/
    #     ]
    #     models_exist = all(os.path.exists(model_dir) for model_dir in model_dirs)
    #     if not models_exist:
    #         print("未找到 PaddleOCR 模型文件，正在下载...")
    #         download_url = self.config['Paths'].get('download_url')#C:\Users\xxxxxxx/.paddleocr.zip
    #         zip_path = os.path.join(home_dir, '.paddleocr.zip')
    #         try:
    #             urllib.request.urlretrieve(download_url, zip_path)
    #             print("下载完成，正在解压...")
    #             with zipfile.ZipFile(zip_path, 'r') as zip_ref:
    #                 zip_ref.extractall(home_dir)
    #             print("模型文件解压完成。")
    #             os.remove(zip_path)
    #         except Exception as e:
    #             print(f"下载和解压模型文件失败: {e}")
    #     else:
    #         print("PaddleOCR 模型文件已存在。")

    def check_and_download_models(self):
        home_dir = os.path.expanduser('~')  # C:\Users\xxxxxxx/
        paddleocr_dir = os.path.join(home_dir, '.paddleocr', 'whl')  # C:\Users\xxxxxxx/.paddleocr/whl/
        model_dirs = [
            os.path.join(paddleocr_dir, 'det', 'ch', 'ch_PP-OCRv4_det_infer'),  # C:\Users\xxxxxxx/.paddleocr/whl/det/ch/ch_PP-OCRv4_det_infer/
            os.path.join(paddleocr_dir, 'rec', 'ch', 'ch_PP-OCRv4_rec_infer'),  # C:\Users\xxxxxxx/.paddleocr/whl/rec/ch/ch_PP-OCRv4_rec_infer/
            os.path.join(paddleocr_dir, 'cls', 'ch_ppocr_mobile_v2.0_cls_infer')  # C:\Users\xxxxxxx/.paddleocr/whl/cls/ch_ppocr_mobile_v2.0_cls_infer/
        ]
        models_exist = all(os.path.exists(model_dir) for model_dir in model_dirs)
        
        if not models_exist:
            print("未找到 PaddleOCR 模型文件，尝试从本地拷贝...")
            zip_path = os.path.join(home_dir, '.paddleocr.zip')
            local_resource_zip = os.path.join(os.path.dirname(__file__), 'resources', 'paddleocr.zip')
            
            try:
                # 尝试从 resources 目录拷贝 paddleocr.zip
                shutil.copy(local_resource_zip, zip_path)
                print("从本地 resources 目录拷贝成功，正在解压...")
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(home_dir)
                print("模型文件解压完成。")
                os.remove(zip_path)
            except Exception as e:
                print(f"从本地拷贝失败: {e}，开始从网络下载...")
                download_url = self.config['Paths'].get('download_url')  # 从配置文件中获取下载链接
                try:
                    urllib.request.urlretrieve(download_url, zip_path)
                    print("下载完成，正在解压...")
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        zip_ref.extractall(home_dir)
                    print("模型文件解压完成。")
                    os.remove(zip_path)
                except Exception as e:
                    print(f"下载和解压模型文件失败: {e}")
        else:
            print("PaddleOCR 模型文件已存在。")
            

    def load_plugins(self):
        plugin_modules = {
            'fastshot.plugin_ocr': 'PluginOCR',
            'fastshot.plugin_ask': 'PluginAsk'
        }
        for module_name, class_name in plugin_modules.items():
            module = importlib.import_module(module_name)
            plugin_class = getattr(module, class_name)
            self.plugins[module_name] = plugin_class()

    def setup_hotkey_listener(self):
        def on_activate_snip():
            print("截图快捷键已激活")
            self.snipping_tool.start_snipping()

        def on_escape():
            self.exit_all_modes()

        def for_canonical(f):
            return lambda k: f(self.listener.canonical(k))

        # 从配置文件获取快捷键
        hotkey_snip_str = self.config['Shortcuts'].get('hotkey_snip', '<shift>+a+s')
        hotkey_snip = keyboard.HotKey(keyboard.HotKey.parse(hotkey_snip_str), on_activate_snip)

        self.listener = keyboard.Listener(
            on_press=for_canonical(hotkey_snip.press),
            on_release=for_canonical(hotkey_snip.release))
        self.listener.start()

        self.listener_escape = keyboard.Listener(
            on_press=for_canonical(lambda key: on_escape() if key == keyboard.Key.esc else None))
        self.listener_escape.start()

    def start_screen_pen_listener(self):
        # 启动 ScreenPen 的键盘监听器线程
        keyboard_thread = threading.Thread(target=self.screen_pen.start_keyboard_listener)
        keyboard_thread.daemon = True
        keyboard_thread.start()

    def on_screenshot(self, img):
        window = ImageWindow(self, img, self.config)
        self.windows.append(window)

    def exit_all_modes(self):
        for window in self.windows:
            if window.img_window.winfo_exists():
                window.exit_edit_mode()

    def run(self):
        self.root.mainloop()

def main():
    app = SnipasteApp()
    app.run()

if __name__ == "__main__":
    main()