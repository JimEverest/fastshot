import tkinter as tk
from pynput import keyboard
import threading
import pyautogui
from screeninfo import get_monitors
import ctypes
import win32gui
import numpy as np
import queue

class ScreenPen:
    def __init__(self, master, config):
        self.config = config
        self.master = master  # 主 Tkinter 根窗口

        # 创建 Toplevel 窗口
        self.pen_window = tk.Toplevel(master)
        self.pen_window.overrideredirect(True)  # 移除窗口装饰（标题栏等）
        self.pen_window.attributes('-topmost', True)  # 窗口置顶
        self.pen_window.config(cursor="pencil", bg="black")  # 设置鼠标为画笔形状，背景黑色

        # 设置唯一的窗口标题
        self.window_title = "ScreenPenOverlay"
        self.pen_window.title(self.window_title)

        # 确保窗口已经被创建
        self.pen_window.update()

        # 创建画布
        self.canvas = tk.Canvas(self.pen_window, bg='black', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # 从配置文件读取画笔参数
        self.pen_color = self.config['ScreenPen'].get('pen_color', 'red')
        self.pen_width = self.config['ScreenPen'].getint('pen_width', 3)
        self.smooth_factor = self.config['ScreenPen'].getint('smooth_factor', 3)

        self.drawing = False  # 初始状态为非绘图模式

        # 初始化撤销和恢复栈
        self.undo_stack = []  # 用于存储所有已完成的路径
        self.redo_stack = []  # 用于存储撤销后的路径
        self.current_path = []  # 当前正在绘制的路径

        # 初始化时不显示窗口
        self.pen_window.withdraw()

        # 鼠标事件绑定
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

        # 初始化队列用于线程间通信
        self.queue = queue.Queue()

    def start_keyboard_listener(self):
        print("Starting keyboard listener")
        # 捕捉热键
        hotkeys = {
            self.config['Shortcuts'].get('hotkey_screenpen_toggle', '<ctrl>+x+c'): lambda: self.queue.put(self.toggle_drawing_mode),
            self.config['Shortcuts'].get('hotkey_screenpen_clear_hide', '<ctrl>+<esc>'): lambda: self.queue.put(self.clear_canvas_and_hide)
        }
        listener = keyboard.GlobalHotKeys(hotkeys)
        listener.start()

        # 开始处理队列中的任务
        self.process_queue()

    def process_queue(self):
        try:
            while True:
                func = self.queue.get_nowait()
                func()  # 在主线程中执行函数
        except queue.Empty:
            pass
        self.master.after(50, self.process_queue)  # 每 50 毫秒检查一次队列

    def get_hwnd(self):
        """
        获取窗口句柄
        """
        hwnd = win32gui.FindWindow(None, self.window_title)
        return hwnd

    def set_window_to_draw(self):
        """
        将窗口设置为绘图模式，确保半透明状态并捕获鼠标事件
        """
        hwnd = self.get_hwnd()
        if hwnd:
            print("Setting window to drawing mode")
            extended_style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            # 确保 WS_EX_LAYERED 样式被设置
            extended_style = extended_style | 0x80000
            # 移除 WS_EX_TRANSPARENT 样式
            extended_style = extended_style & ~0x20
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, extended_style)
            self.set_window_opacity(0.15)  # 设置透明度为 15%
        else:
            print("Could not find window handle to set drawing mode.")

    def set_window_opacity(self, opacity):
        """
        使用 Windows API 设置 Tkinter 窗口的透明度
        """
        hwnd = self.get_hwnd()
        if hwnd:
            print(f"Setting window opacity to {opacity * 100}%")
            ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, int(opacity * 255), 0x2)
        else:
            print("Could not find window handle to set opacity.")

    def toggle_drawing_mode(self):
        if self.drawing:
            print("Exiting drawing mode")
            self.drawing = False
            self.set_window_transparent()
        else:
            print("Entering drawing mode")
            self.drawing = True
            screen_info = self.get_current_screen_info()
            self.pen_window.geometry(f"{screen_info['width']}x{screen_info['height']}+{screen_info['x']}+{screen_info['y']}")
            self.pen_window.deiconify()
            self.set_window_to_draw()
            self.redraw_all_paths()
            # 绑定键盘事件
            self.pen_window.focus_set()
            self.pen_window.bind("<Escape>", self.on_escape)
            self.pen_window.bind("<Control-z>", lambda event: self.undo_last_action())
            self.pen_window.bind("<Control-y>", lambda event: self.redo_last_action())

    def set_window_transparent(self):
        """
        设置窗口为鼠标穿透和透明模式
        """
        hwnd = self.get_hwnd()
        if hwnd:
            print("Setting window transparent and click-through")
            extended_style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            extended_style = extended_style | 0x80000 | 0x20  # 设置透明和鼠标穿透
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, extended_style)
            ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, 0, 0x1)
        else:
            print("Could not find window handle to set transparency.")

    def on_escape(self, event=None):
        if self.drawing:
            self.toggle_drawing_mode()

    def get_current_screen_info(self):
        """
        获取当前鼠标所在的屏幕尺寸和位置
        """
        mouse_x, mouse_y = pyautogui.position()
        for monitor in get_monitors():
            if monitor.x <= mouse_x <= monitor.x + monitor.width and monitor.y <= mouse_y <= monitor.y + monitor.height:
                print(f"Mouse is on screen: {monitor}")
                return {'x': monitor.x, 'y': monitor.y, 'width': monitor.width, 'height': monitor.height}

        # 默认返回主屏幕信息
        print("Mouse is not on any screen, defaulting to primary screen.")
        screen_width, screen_height = pyautogui.size()
        return {'x': 0, 'y': 0, 'width': screen_width, 'height': screen_height}


    def on_button_press(self, event):
        if self.drawing:
            self.last_x, self.last_y = event.x, event.y
            self.current_path = [(self.last_x, self.last_y)]  # 开始记录新的路径
            print(f"Mouse button pressed at: ({self.last_x}, {self.last_y})")

    def on_mouse_move(self, event):
        if self.drawing:
            x, y = event.x, event.y
            print(f"Mouse moved to: ({x}, {y})")
            self.current_path.append((x, y))  # 记录路径点
            self.redraw_current_path()  # 仅重绘当前路径

    def on_button_release(self, event):
        print("Mouse button released")
        if self.drawing and self.current_path:
            # 将当前路径推入撤销栈（仅保留平滑后的路径）
            smoothed_path = self.apply_catmull_rom_spline(self.current_path) if len(self.current_path) >= 4 else self.current_path
            self.undo_stack.append(smoothed_path)  # 保存平滑后的路径
            self.current_path = []  # 清空当前路径
            self.redo_stack.clear()  # 清空恢复栈
            self.redraw_all_paths()  # 重绘所有路径以保持当前绘制的内容

    def redraw_current_path(self):
        """
        仅重绘当前正在绘制的路径，保留之前的路径
        """
        # 删除当前路径的绘制内容
        self.canvas.delete("current_line")

        # 绘制平滑后的路径
        if len(self.current_path) >= 4:
            smooth_path = self.apply_catmull_rom_spline(self.current_path)
            for i in range(len(smooth_path) - 1):
                self.canvas.create_line(smooth_path[i], smooth_path[i + 1], fill=self.pen_color, width=self.pen_width, tags="current_line")
        else:
            # 如果点不足以生成样条曲线，直接绘制原始线条
            for i in range(len(self.current_path) - 1):
                self.canvas.create_line(self.current_path[i], self.current_path[i + 1], fill=self.pen_color, width=self.pen_width, tags="current_line")

    def apply_catmull_rom_spline(self, points):
        """
        应用 Catmull-Rom 样条曲线平滑路径
        """
        def catmull_rom(p0, p1, p2, p3, t):
            """
            Catmull-Rom 样条曲线公式
            """
            t2 = t * t
            t3 = t2 * t
            return (
                0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3),
                0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            )

        # 生成样条曲线点
        smooth_points = []
        for i in range(len(points) - 3):
            p0, p1, p2, p3 = points[i], points[i + 1], points[i + 2], points[i + 3]
            for t in np.linspace(0, 1, self.smooth_factor):
                smooth_points.append(catmull_rom(p0, p1, p2, p3, t))

        return smooth_points

    def redraw_all_paths(self):
        """
        重绘所有的路径，包括已完成的和当前正在绘制的路径
        """
        self.canvas.delete("all")  # 清除所有画布内容
        for path in self.undo_stack:
            self.draw_path(path)  # 绘制所有已保存的路径
        self.redraw_current_path()  # 重新绘制当前路径

    def draw_path(self, path):
        """
        绘制保存的路径
        """
        if len(path) < 2:
            return
        for i in range(len(path) - 1):
            self.canvas.create_line(path[i], path[i + 1], fill=self.pen_color, width=self.pen_width)

    def undo_last_action(self):
        if self.undo_stack:
            print("Undo last action")
            last_path = self.undo_stack.pop()  # 从撤销栈中弹出最后一条路径
            self.redo_stack.append(last_path)  # 将其推入恢复栈
            self.redraw_all_paths()  # 重新绘制所有路径

    def redo_last_action(self):
        if self.redo_stack:
            print("Redo last action")
            self.undo_stack.append(last_path)  # 将其推入撤销栈
            self.redraw_all_paths()  # 重新绘制所有路径

    def clear_canvas(self, keep_history=False):
        print("Clearing canvas...")
        self.canvas.delete("all")  # 清除所有画布内容
        if not keep_history:
            self.undo_stack.clear()  # 清空撤销栈
            self.redo_stack.clear()  # 清空恢复栈

    def clear_canvas_and_hide(self):
        print("Clearing canvas and hiding...")
        self.clear_canvas()
        self.pen_window.withdraw()  # 隐藏窗口