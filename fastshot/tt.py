import logging
from pynput import keyboard
from pynput.keyboard import Key, KeyCode

# 设置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("hotkeys_pynput.log"),
        logging.StreamHandler()
    ]
)

# 定义要监听的组合键
COMBINATION_TOGGLE_TOPMOST = {Key.cmd, Key.shift, KeyCode.from_char('?')}
COMBINATION_TOGGLE_NOT_TOPMOST = {Key.cmd, Key.shift, KeyCode.from_char('|')}

# 当前按下的键
current_keys = set()

def on_press(key):
    logging.debug(f"按下键: {key}")
    current_keys.add(key)

    if COMBINATION_TOGGLE_TOPMOST.issubset(current_keys):
        logging.info("检测到热键: Win + Shift + ?")
        toggle_always_on_top()
    
    if COMBINATION_TOGGLE_NOT_TOPMOST.issubset(current_keys):
        logging.info("检测到热键: Win + Shift + |")
        toggle_always_on_top()

def on_release(key):
    logging.debug(f"释放键: {key}")
    try:
        current_keys.remove(key)
    except KeyError:
        pass

def toggle_always_on_top():
    import win32gui
    import win32con

    hwnd = win32gui.GetForegroundWindow()
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
            if result:
                logging.info(f"窗口 '{window_title}' 已取消总在最前")
            else:
                logging.error(f"无法取消窗口 '{window_title}' 的总在最前属性")
        else:
            # 设置为总在最前
            result = win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
            )
            if result:
                logging.info(f"窗口 '{window_title}' 已设置为总在最前")
            else:
                logging.error(f"无法设置窗口 '{window_title}' 为总在最前")
    except Exception as e:
        logging.exception(f"切换窗口总在最前属性时发生异常: {e}")

def main():
    with keyboard.Listener(
        on_press=on_press,
        on_release=on_release) as listener:
        logging.info("热键监听已启动，开始监听热键事件... 按下 Ctrl + C 退出")
        listener.join()

if __name__ == "__main__":
    main()