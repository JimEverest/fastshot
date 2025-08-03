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
import threading
# Import your Flask app
import sys
# sys.path.append(os.path.join(os.path.dirname(__file__), 'web'))
# from fastshot.web.web_app import app as flask_app 
from tkinter import filedialog
from PIL import Image, UnidentifiedImageError

# print(f"flask_app: {flask_app}")
# print(f"flask_app type: {type(flask_app)}")

from fastshot.snipping_tool import SnippingTool
from fastshot.image_window import ImageWindow
from fastshot.screen_pen import ScreenPen  # 导入 ScreenPen
from fastshot.window_control import HotkeyListener, load_config
from fastshot.ask_dialog import AskDialog
from fastshot.session_manager import SessionManager  # 导入 SessionManager
from fastshot.cloud_sync import CloudSyncManager  # 导入 CloudSyncManager

# Import version information
try:
    from fastshot import __version__, __author__, __description__
except ImportError:
    # Fallback for development environment
    __version__ = "1.4.1-dev"
    __author__ = "Jim T"
    __description__ = "A versatile screen capturing tool with annotation and OCR features"


import importlib
import pkgutil
import time


#plugins
from fastshot.plugin_ocr import PluginOCR
# from fastshot.plugin_ask import PluginAsk

# --- New Class: VisibilityIndicator ---
class VisibilityIndicator(tk.Toplevel):
    """A small window to show the count of hidden image windows."""
    def __init__(self, master, count):
        super().__init__(master)
        self.overrideredirect(True)  # No window decorations
        self.attributes('-topmost', True) # Always on top
        self.attributes('-alpha', 0.85) # Slightly transparent
        # Make window non-interactive (click-through) - Windows specific
        if os.name == 'nt':
            self.after(10, self._set_click_through) # Delay needed for HWND

        self.label = tk.Label(self, text=str(count), font=("Arial", 14, "bold"), bg="#333333", fg="white", padx=8, pady=4)
        self.label.pack()

        # Position in top-right corner of the primary monitor
        self.update_idletasks() # Ensure window size is calculated
        primary_monitor = get_monitors()[0]
        window_width = self.winfo_width()
        window_height = self.winfo_height()
        # Position near top-right, with some padding
        x_pos = primary_monitor.x + primary_monitor.width - window_width - 30
        y_pos = primary_monitor.y + 30
        self.geometry(f"+{x_pos}+{y_pos}")

    def _set_click_through(self):
        """Set WS_EX_TRANSPARENT style for click-through."""
        try:
            hwnd = self.winfo_id()
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20) # GWL_EXSTYLE
            style = style | 0x80000 | 0x20 # WS_EX_LAYERED | WS_EX_TRANSPARENT
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style)
            ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, int(0.85 * 255), 0x2) # LWA_ALPHA
        except Exception as e:
            print(f"Error setting click-through: {e}")

    def update_count(self, count):
        """Updates the displayed count."""
        self.label.config(text=str(count))
        # Recalculate position in case text size changes width
        self.update_idletasks()
        primary_monitor = get_monitors()[0]
        window_width = self.winfo_width()
        x_pos = primary_monitor.x + primary_monitor.width - window_width - 30
        y_pos = primary_monitor.y + 30
        self.geometry(f"+{x_pos}+{y_pos}")


    def destroy(self):
        """Destroys the indicator window."""
        super().destroy()

class SnipasteApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.app = self  # Set reference to self in root
        self.monitors = get_monitors()
        self.snipping_tool = SnippingTool(self.root, self.monitors, self.create_image_window)
        self.windows = []
        self.plugins = {}
        
        # Add state for visibility toggle
        self.all_windows_hidden = False
        self.visibility_indicator = None
        
        self.config = self.load_config()
        self.print_config_info()
        self.check_and_download_models()
        self.load_plugins()
        self.plugins['fastshot.plugin_ocr']=PluginOCR()
        # self.plugins['fastshot.plugin_ask']=PluginAsk()

        # Initialize the hotkey listener
        self.ask_dialog = None  # Reference to AskDialog instance
        self.listener = HotkeyListener(self.config, self.root, self)
        self.listener.start()

        # Initialize session manager
        self.session_manager = SessionManager(self)
        
        # Initialize cloud sync manager
        self.cloud_sync = CloudSyncManager(self)

        # Initialize notes manager and cache manager
        from fastshot.notes_manager import NotesManager
        from fastshot.notes_cache import NotesCacheManager
        self.notes_manager = NotesManager(self)
        self.notes_cache = NotesCacheManager()
        
        # Initialize quick notes UI (lazy initialization)
        self.quick_notes_ui = None

        # Initialize ScreenPen
        enable_screenpen = self.config['ScreenPen'].getboolean('enable_screenpen', True)
        if enable_screenpen:
            self.screen_pen = ScreenPen(self.root, self.config)
            self.screen_pen.start_keyboard_listener()
        else:
            self.screen_pen = None

        # Start the Flask web app
        # self.start_flask_app()


    def load_plugins(self):
        plugins_dir = os.path.join(os.path.dirname(__file__), 'plugins')
        sys.path.insert(0, plugins_dir)

        for finder, name, ispkg in pkgutil.iter_modules([plugins_dir]):
            try:
                plugin_module = importlib.import_module(name)
                plugin_info = plugin_module.get_plugin_info()
                self.plugins[plugin_info['id']] = {
                    'module': plugin_module,
                    'info': plugin_info
                }
                print(f"Loaded plugin: {plugin_info['name']}")
            except Exception as e:
                print(f"Failed to load plugin {name}: {e}")

    def setup_plugin_hotkeys(self):
        for plugin_id, plugin_data in self.plugins.items():
            plugin_info = plugin_data['info']
            if plugin_info.get('enabled', True):
                shortcut_key = plugin_info.get('default_shortcut')
                press_times = int(plugin_info.get('press_times', 1))
                self.listener.register_plugin_hotkey(
                    plugin_id, shortcut_key, press_times)


                    
    # def start_flask_app(self):
    #     def run_flask():
    #         try:
    #             flask_app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)
    #         except Exception as e:
    #             print(f"Failed to start Flask app: {e}")

    #     threading.Thread(target=run_flask, daemon=True).start()
    #     print("Flask web app started on http://127.0.0.1:5000")

    def open_global_ask_dialog(self):
        if self.ask_dialog:
            if self.ask_dialog.is_minimized:
                # Restore minimized dialog
                self.ask_dialog.dialog_window.deiconify()
                self.ask_dialog.is_minimized = False
            else:
                # Bring existing dialog to front
                self.ask_dialog.dialog_window.lift()
        else:
            # Create new dialog
            self.ask_dialog = AskDialog()

        
    def load_config(self):
        config = configparser.ConfigParser()
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
        if not os.path.exists(config_path):
            # Create default config file
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
                'hotkey_screenpen_clear_hide': '<ctrl>+<esc>',
                'hotkey_ask_dialog_key': 'ctrl',
                'hotkey_ask_dialog_count': '4',
                'hotkey_ask_dialog_time_window': '1.0',
                'hotkey_toggle_visibility': '<shift>+<f1>',
                'hotkey_load_image': '<shift>+<f2>',
                'hotkey_reposition_windows': '<shift>+<f3>',
                'hotkey_save_session': '<shift>+<f4>',
                'hotkey_load_session': '<shift>+<f5>',
                'hotkey_session_manager': '<shift>+<f6>',
                'hotkey_quick_notes': '<shift>+<f7>'
            }
            config['ScreenPen'] = {
                'enable_screenpen': 'True',
                'pen_color': 'red',
                'pen_width': '3',
                'smooth_factor': '3',
                'overlay_opacity': '0.4'
            }
            with open(config_path, 'w', encoding='utf-8') as configfile:
                config.write(configfile)
        else:
            config.read(config_path, encoding='utf-8')
        self.config_path = config_path
        return config

    def print_config_info(self):
        # Print version information
        print("=" * 60)
        print(f"🚀 Fastshot v{__version__}")
        # print(f"📝 {__description__}")
        # print(f"👨‍💻 Author: {__author__}")
        print("=" * 60)
        print()
        
        print(f"Config file path: {self.config_path}")
        print("Shortcut settings:")
        shortcut_descriptions = {
            'hotkey_snip': 'Start snipping',
            'hotkey_paint': 'Enable paint mode',
            'hotkey_text': 'Enable text mode',
            'hotkey_screenpen_toggle': 'Toggle screen pen mode',
            'hotkey_undo': 'Undo last action',
            'hotkey_redo': 'Redo last action',
            'hotkey_screenpen_exit': 'Exit screen pen mode',
            'hotkey_screenpen_clear_hide': 'Clear pen and hide',
            'hotkey_ask_dialog_key': 'Ask Dialog key',
            'hotkey_ask_dialog_count': 'Ask Dialog press count',
            'hotkey_ask_dialog_time_window': 'Ask Dialog time window',
            'hotkey_toggle_visibility': 'Toggle All Image Windows Visibility',
            'hotkey_load_image': 'Load Image from File',
            'hotkey_reposition_windows': 'Reposition All Image Windows to Origin',
            'hotkey_save_session': 'Save Current Session',
            'hotkey_load_session': 'Load Session',
            'hotkey_session_manager': 'Open Session Manager',
            'hotkey_quick_notes': 'Open Quick Notes'
        }
        for key, desc in shortcut_descriptions.items():
            value = self.config['Shortcuts'].get(key, '')
            print(f"{desc}: {value}")

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


    def create_image_window(self, img):
        """Creates a new floating ImageWindow from a PIL Image object."""
        if not isinstance(img, Image.Image):
            print("Error: create_image_window requires a PIL Image object.")
            return

        window = ImageWindow(self, img, self.config)
        # If windows are currently hidden, hide the new one immediately
        if self.all_windows_hidden:
            window.hide()
            # Update indicator count
            # Calculate count *after* potentially hiding the new window
            hidden_count = sum(1 for w in self.windows if w.is_hidden and w.img_window.winfo_exists())
            if window.is_hidden: # Add 1 if the new window was successfully hidden
                 hidden_count += 1
            self.show_visibility_indicator(hidden_count)

        self.windows.append(window)

    def load_image_from_dialog(self):
        """Opens a file dialog to load an image and creates an ImageWindow."""
        file_path = filedialog.askopenfilename(
            title="Open Image File",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff"), ("All Files", "*.*")]
        )

        if not file_path:
            print("No file selected.")
            return

        try:
            print(f"Attempting to load image: {file_path}")
            img = Image.open(file_path)
            # Ensure image is in RGBA format for consistency with screenshots?
            # img = img.convert("RGBA") # Optional: uncomment if needed
            self.create_image_window(img) # Use the renamed method
            print(f"Successfully loaded and displayed image: {file_path}")
        except FileNotFoundError:
            print(f"Error: File not found at {file_path}")
            # Optionally show a user-friendly error message
            # messagebox.showerror("Error", f"File not found:\n{file_path}")
        except UnidentifiedImageError:
            print(f"Error: Cannot identify image file. Is it a valid image format? Path: {file_path}")
            # messagebox.showerror("Error", f"Cannot open image file:\n{file_path}\n\nPlease select a valid image.")
        except Exception as e:
            print(f"An unexpected error occurred while loading image: {e}")
            # messagebox.showerror("Error", f"An error occurred:\n{e}")

    def exit_all_modes(self):
        for window in self.windows:
            if window.img_window.winfo_exists():
                window.exit_edit_mode()

    def run(self):
        self.root.snipping_tool = self.snipping_tool
        self.root.mainloop()

    # --- New Methods for Visibility Toggle ---
    def toggle_all_image_windows_visibility(self):
        """Toggles the visibility of all active ImageWindow instances."""
        self.all_windows_hidden = not self.all_windows_hidden
        hidden_count = 0

        # Iterate over a copy in case the list is modified during iteration (e.g., by closing)
        for window in list(self.windows):
            if window.img_window.winfo_exists():
                if self.all_windows_hidden:
                    window.hide()
                    hidden_count += 1
                else:
                    # Only show if it was previously hidden by this toggle
                    if window.is_hidden:
                        window.show()

        # Update or remove the indicator
        if self.all_windows_hidden and hidden_count > 0:
            self.show_visibility_indicator(hidden_count)
            print(f"Hid {hidden_count} windows.")
        else:
            # Ensure all windows are shown if toggle is off
            if not self.all_windows_hidden:
                 for window in list(self.windows):
                     if window.img_window.winfo_exists() and window.is_hidden:
                         window.show()
            self.hide_visibility_indicator()
            print("Showing all windows.")


    def show_visibility_indicator(self, count):
        """Creates or updates the visibility indicator."""
        if self.visibility_indicator and self.visibility_indicator.winfo_exists():
            self.visibility_indicator.update_count(count)
        else:
            # Ensure no old indicator exists before creating a new one
            self.hide_visibility_indicator()
            self.visibility_indicator = VisibilityIndicator(self.root, count)

    def hide_visibility_indicator(self):
        """Destroys the visibility indicator if it exists."""
        if self.visibility_indicator and self.visibility_indicator.winfo_exists():
            self.visibility_indicator.destroy()
        self.visibility_indicator = None

    def update_indicator_on_close(self):
        """Called when an ImageWindow is closed to update the indicator if needed."""
        if self.all_windows_hidden:
            hidden_count = sum(1 for w in self.windows if w.is_hidden and w.img_window.winfo_exists())
            if hidden_count > 0:
                self.show_visibility_indicator(hidden_count)
            else:
                # If the last hidden window was closed, turn off the toggle state
                self.all_windows_hidden = False
                self.hide_visibility_indicator()
    # --- End New Methods ---

    def reposition_all_image_windows(self):
        """Repositions all active ImageWindow instances to the primary monitor's origin."""
        try:
            # Get primary monitor info
            monitors = get_monitors()
            primary_monitor = None
            for monitor in monitors:
                if monitor.is_primary:
                    primary_monitor = monitor
                    break
            
            # Fallback to first monitor if no primary found
            if not primary_monitor and monitors:
                primary_monitor = monitors[0]
            
            if not primary_monitor:
                print("No monitors found for repositioning.")
                return

            # Start position at primary monitor's origin
            start_x = primary_monitor.x
            start_y = primary_monitor.y
            offset_step = 30  # Pixels to offset each window to avoid complete overlap

            repositioned_count = 0
            active_windows = []

            # Get all active (existing) image windows
            for window in self.windows:
                if window.img_window.winfo_exists() and not window.is_hidden:
                    active_windows.append(window)

            if not active_windows:
                print("No active image windows to reposition.")
                return

            # Reposition each window with a small offset
            for i, window in enumerate(active_windows):
                try:
                    new_x = start_x + (i * offset_step)
                    new_y = start_y + (i * offset_step)
                    
                    # Ensure the window doesn't go outside the primary monitor bounds
                    # Get window dimensions first
                    window.img_window.update_idletasks()  # Ensure geometry is current
                    window_width = window.img_window.winfo_width()
                    window_height = window.img_window.winfo_height()
                    
                    # Check boundaries and adjust if necessary
                    max_x = primary_monitor.x + primary_monitor.width - window_width
                    max_y = primary_monitor.y + primary_monitor.height - window_height
                    
                    if new_x > max_x:
                        new_x = primary_monitor.x  # Wrap back to left edge
                        new_y += offset_step * 2  # Move down more to avoid overlap
                    
                    if new_y > max_y:
                        new_y = primary_monitor.y  # Wrap back to top
                    
                    # Move the window
                    window.img_window.geometry(f"+{new_x}+{new_y}")
                    repositioned_count += 1
                    print(f"Repositioned window {i+1} to ({new_x}, {new_y})")
                    
                except Exception as e:
                    print(f"Error repositioning window {i+1}: {e}")
                    continue

            print(f"Successfully repositioned {repositioned_count} image windows to primary monitor origin.")

        except Exception as e:
            print(f"Error during reposition operation: {e}")

    def save_session_dialog(self):
        """Shows dialog to save the current session."""
        if not self.windows:
            from tkinter import messagebox
            messagebox.showinfo("No Windows", "No image windows to save.")
            return
        
        self.session_manager.save_session_with_dialog()

    def load_session_dialog(self):
        """Shows dialog to load a session."""
        self.session_manager.load_session_with_dialog()
    
    def open_session_manager(self):
        """Opens the session manager UI."""
        try:
            print("DEBUG: open_session_manager called")
            print(f"DEBUG: Current working directory: {os.getcwd()}")
            print(f"DEBUG: Python path: {sys.path}")
            
            print("DEBUG: Attempting to import SessionManagerUI")
            from fastshot.session_manager_ui import SessionManagerUI
            print("DEBUG: SessionManagerUI imported successfully")
            
            print(f"DEBUG: Creating SessionManagerUI with app={self}")
            session_ui = SessionManagerUI(self)
            print("DEBUG: SessionManagerUI created successfully")
            
            print("DEBUG: Calling session_ui.show()")
            session_ui.show()
            print("DEBUG: session_ui.show() completed")
            
        except ImportError as e:
            print(f"ERROR: Failed to import SessionManagerUI: {e}")
            import traceback
            traceback.print_exc()
        except Exception as e:
            print(f"ERROR in open_session_manager: {e}")
            import traceback
            traceback.print_exc()
    
    def open_quick_notes(self):
        """Opens the Quick Notes UI."""
        try:
            print("DEBUG: open_quick_notes called")
            
            if not self.quick_notes_ui:
                print("DEBUG: Creating QuickNotesUI instance")
                from fastshot.quick_notes_ui import QuickNotesUI
                self.quick_notes_ui = QuickNotesUI(self)
                print("DEBUG: QuickNotesUI created successfully")
            
            print("DEBUG: Calling show_window()")
            self.quick_notes_ui.show_window()
            print("DEBUG: show_window() completed")
            
        except ImportError as e:
            print(f"ERROR: Failed to import QuickNotesUI: {e}")
            import traceback
            traceback.print_exc()
        except Exception as e:
            print(f"ERROR in open_quick_notes: {e}")
            import traceback
            traceback.print_exc()
    
    def update_screen_pen_config(self):
        """Update Screen Pen configuration after settings change."""
        if self.screen_pen:
            # Reload config file
            self.config.read(self.config_path, encoding='utf-8')
            # Update Screen Pen with new config
            self.screen_pen.update_config(self.config)
            print("Screen Pen configuration updated")

def main():
    app = SnipasteApp()
    app.run()

if __name__ == "__main__":
    main()