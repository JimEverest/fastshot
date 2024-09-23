import ctypes
from ctypes import wintypes
from pynput import keyboard
import win32gui
import win32con
import win32process
import logging

# 定义 Windows API 函数
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32  # 定义 kernel32

# 设置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
    # handlers=[
    #     logging.FileHandler("hotkeys_pynput.log"),
    #     logging.StreamHandler()
    # ]
)

# 常量
GWL_EXSTYLE = -20  # 用于获取扩展窗口样式的常量
WS_EX_LAYERED = 0x80000
LWA_ALPHA = 0x2

# 定义一个全局变量来存储透明度
current_window_opacity = 1.0  # 默认不透明

# 获取前台窗口
def get_foreground_window():
    hwnd = user32.GetForegroundWindow()
    if hwnd and user32.IsWindow(hwnd) and user32.IsWindowVisible(hwnd):
        # 获取窗口的进程ID和程序名
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        process_handle = open_process(pid)
        if process_handle:
            executable = win32process.GetModuleFileNameEx(process_handle, None)
            window_title = win32gui.GetWindowText(hwnd)
            window_class = win32gui.GetClassName(hwnd)
            print(f"当前激活窗口句柄: {hwnd}, 标题: {window_title}, 程序: {executable}, 窗口类: {window_class}")
            return hwnd
        else:
            print(f"无法打开进程，PID: {pid}")
            return None
    else:
        print("无法获取有效的前台窗口句柄或窗口不可见")
        return None

def open_process(pid):
    """通过 PID 打开进程句柄，返回进程句柄"""
    PROCESS_ALL_ACCESS = (0x000F0000 | 0x00100000 | 0xFFF)
    return kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)

# 设置窗口透明度
def set_window_opacity(hwnd, opacity):
    """设置窗口透明度，确保在 10% 到 100% 之间"""
    global current_window_opacity
    if hwnd:
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)  # 使用 GWL_EXSTYLE
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)
        
        # 确保透明度在 10% 到 100% 之间
        opacity = max(0.1, min(opacity, 1.0))  # 限制透明度在 [0.1, 1.0]
        current_window_opacity = opacity  # 保存当前透明度值
        print(f"设置透明度：{opacity * 100}%")
        user32.SetLayeredWindowAttributes(hwnd, 0, int(255 * opacity), LWA_ALPHA)

def get_window_opacity(hwnd):
    """获取窗口当前透明度，返回全局存储的透明度值"""
    global current_window_opacity
    return current_window_opacity  # 直接返回存储的透明度值

# 切换总在最前状态
def toggle_always_on_top():
    hwnd = get_foreground_window()
    if hwnd == 0:
        logging.warning("未能获取当前活动窗口句柄")
        return
    window_title = win32gui.GetWindowText(hwnd)
    logging.info(f"当前活动窗口句柄: {hwnd}, 标题: {window_title}")

    try:
        # 检查当前窗口是否为总在最前
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        is_topmost = bool(ex_style & win32con.WS_EX_TOPMOST)

        if is_topmost:
            # 取消总在最前
            result = win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_NOTOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
            )
            # if result:
            #     logging.info(f"窗口 '{window_title}' 已取消总在最前")
            # else:
            #     logging.error(f"无法取消窗口 '{window_title}' 的总在最前属性")
        else:
            # 设置为总在最前
            result = win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
            )
            # if result:
            #     logging.info(f"窗口 '{window_title}' 已设置为总在最前")
            # else:
            #     logging.error(f"无法设置窗口 '{window_title}' 为总在最前")
    except Exception as e:
        logging.exception(f"切换窗口总在最前属性时发生异常: {e}")

# 热键处理器
class HotkeyListener:
    def __init__(self, config):
        self.listener = keyboard.GlobalHotKeys({
            config['Shortcuts'].get('hotkey_topmost_on'): self.toggle_topmost_on,
            config['Shortcuts'].get('hotkey_topmost_off'): self.toggle_topmost_off,
            config['Shortcuts'].get('hotkey_opacity_down'): self.decrease_opacity,
            config['Shortcuts'].get('hotkey_opacity_up'): self.increase_opacity
        })

    def toggle_topmost_on(self):
        logging.info("检测到热键: 总在最前")
        toggle_always_on_top()

    def toggle_topmost_off(self):
        logging.info("检测到热键: 取消总在最前")
        toggle_always_on_top()

    def decrease_opacity(self):
        """减少窗口透明度，每次减少 10%，最低到 10%"""
        hwnd = get_foreground_window()
        if hwnd:
            current_opacity = get_window_opacity(hwnd)
            print(f"当前透明度：{current_opacity * 100}%")
            
            # 每次减少 10%
            new_opacity = max(0.1, current_opacity - 0.1)
            set_window_opacity(hwnd, new_opacity)
            print(f"窗口透明度已减少至 {new_opacity * 100:.0f}%")

    def increase_opacity(self):
        """增加窗口透明度，每次增加 10%，最高到 100%"""
        hwnd = get_foreground_window()
        if hwnd:
            current_opacity = get_window_opacity(hwnd)
            print(f"当前透明度：{current_opacity * 100}%")
            
            # 每次增加 10%
            new_opacity = min(1.0, current_opacity + 0.1)
            set_window_opacity(hwnd, new_opacity)
            print(f"窗口透明度已增加至 {new_opacity * 100:.0f}%")

    def start(self):
        self.listener.start()

    def stop(self):
        self.listener.stop()

# 从配置文件加载热键
def load_config():
    config = {
        'hotkey_topmost_on': '<cmd>+<shift>+/',
        'hotkey_topmost_off': '<cmd>+<shift>+\\',
        'hotkey_opacity_down': '<cmd>+<shift>+[',
        'hotkey_opacity_up': '<cmd>+<shift>+]'
    }
    return config

# 主程序入口
if __name__ == '__main__':
    config = load_config()  # 加载配置
    listener = HotkeyListener(config)
    logging.info("正在监听热键...")
    listener.start()
    input("按 Enter 停止程序...")
    listener.stop()