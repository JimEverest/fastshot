import tkinter as tk
from tkinter import ttk, messagebox
from .components.shortcuts_frame import ShortcutsFrame
from .components.screenpen_frame import ScreenPenFrame
from .components.genai_frame import GenAIFrame
from .components.notes_sync_frame import NotesSyncFrame
from .components.calendar_sync_frame import CalendarSyncFrame
from .settings_manager import SettingsManager

class SettingsWindow(tk.Toplevel):
    def __init__(self, parent=None, active_tab=None, app=None):
        super().__init__(parent)
        self.title("Fastshot Settings")
        self.settings_manager = SettingsManager()
        self.app = app  # Reference to main app for configuration updates

        # 创建标签页
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill='both', padx=5, pady=5)

        # 添加设置页面
        self.shortcuts_frame = ShortcutsFrame(self.notebook, self.settings_manager)
        self.screenpen_frame = ScreenPenFrame(self.notebook, self.settings_manager)
        self.genai_frame = GenAIFrame(self.notebook, self.settings_manager)
        self.notes_sync_frame = NotesSyncFrame(self.notebook, self.settings_manager)
        self.calendar_sync_frame = CalendarSyncFrame(self.notebook, self.settings_manager, app=app)

        # 添加到notebook
        self.notebook.add(self.shortcuts_frame, text='Shortcuts')
        self.notebook.add(self.screenpen_frame, text='Screen Pen')
        self.notebook.add(self.genai_frame, text='GenAI')
        self.notebook.add(self.notes_sync_frame, text='Notes Sync')
        self.notebook.add(self.calendar_sync_frame, text='Outlook Calendar')
        
        # 如果指定了活动标签页，切换到该页
        if active_tab is not None:
            self.notebook.select(active_tab)
        
        # 底部按钮
        self.create_buttons()
    
    def create_buttons(self):
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(btn_frame, text="Save", command=self.save_settings).pack(side='right', padx=5)
        ttk.Button(btn_frame, text="Reset", command=self.reset_settings).pack(side='right', padx=5)
    
    def save_settings(self):
        # 获取所有设置
        shortcuts_settings = self.shortcuts_frame.get_settings()
        screenpen_settings = self.screenpen_frame.get_settings()
        genai_settings = self.genai_frame.get_settings()
        notes_sync_settings = self.notes_sync_frame.get_settings()
        calendar_sync_settings = self.calendar_sync_frame.get_settings()

        # 更新到配置管理器
        self.settings_manager.update_section('Shortcuts', shortcuts_settings)
        self.settings_manager.update_section('ScreenPen', screenpen_settings)
        self.settings_manager.update_section('PowerGenAI', genai_settings)
        self.settings_manager.update_section('NotesSync', notes_sync_settings)
        self.settings_manager.update_section('CalendarSync', calendar_sync_settings)

        # 保存所有设置
        self.settings_manager.save_settings()

        # 通知主应用更新Screen Pen配置
        if self.app and hasattr(self.app, 'update_screen_pen_config'):
            self.app.update_screen_pen_config()

        # Reload notes sync config
        if self.app and hasattr(self.app, 'notes_sync'):
            if hasattr(self.app, 'config_path'):  # the app's own copy of config.ini follows what was just saved
                self.app.config.read(self.app.config_path, encoding='utf-8')
            self.app.notes_sync._load_config()
        if self.app and getattr(self.app, 'calendar_sync', None) is not None:
            self.app.calendar_sync.reload()  # the automatic sync follows the new switch and interval at once
        
        # 显示保存成功消息
        from tkinter import messagebox
        messagebox.showinfo("Settings", "Settings saved successfully!")
        
        self.destroy()
    
    def reset_settings(self):
        # 重置设置
        if messagebox.askyesno("Reset Settings", "Are you sure to reset all settings?"):
            self.settings_manager.reset_settings()
            self.destroy() 