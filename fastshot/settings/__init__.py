from .settings_window import SettingsWindow

def show_settings(parent=None, active_tab=None, app=None):
    """
    显示设置窗口
    
    Args:
        parent: 父窗口
        active_tab: 要激活的标签页索引(0-based)
        app: 主应用引用，用于配置更新回调
    """
    settings_window = SettingsWindow(parent, active_tab, app)
    settings_window.grab_set()  # 模态窗口
    return settings_window 