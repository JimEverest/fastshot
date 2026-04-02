# Fastshot: Windows → macOS 移植备忘录

> 迁移时间：2026年3月底，耗时约3天
> 涉及修改：17个文件，+1497行 / -1027行
> 新增模块：`fastshot/app_platform/` 平台抽象层（4个文件）

---

## 目录

1. [架构层面的改动](#1-架构层面的改动)
2. [pynput 热键系统（最大的坑）](#2-pynput-热键系统最大的坑)
3. [截图引擎 (SnippingTool)](#3-截图引擎-snippingtool)
4. [UI / Tkinter 兼容性](#4-ui--tkinter-兼容性)
5. [GenAI 集成](#5-genai-集成)
6. [插件系统 & 工具](#6-插件系统--工具)
7. [踩坑一览表](#7-踩坑一览表)
8. [未来注意事项](#8-未来注意事项)

---

## 1. 架构层面的改动

### 1.1 新建平台抽象层 `fastshot/app_platform/`

Windows 版直接 import `win32gui`, `ctypes`, `screeninfo` 等，macOS 上全部不可用。解决方案：新建平台抽象层。

```
fastshot/app_platform/
├── __init__.py      # 统一入口，自动 dispatch
├── base.py          # MonitorInfo, get_monitors() dispatcher
├── macos.py         # NSScreen 多显示器检测, macOS 剪贴板, 窗口控制
└── windows.py       # Win32 原有逻辑封装
```

**关键设计**：`get_monitors()` 返回 **逻辑坐标（points）** 而非物理像素。Tkinter 在 macOS 上使用 points，而 `mss` 截图使用物理像素 —— 两者不能混用。

### 1.2 条件化 Windows 专有 import

所有 `import ctypes`, `import win32gui`, `import win32con` 等改为条件导入：

```python
_IS_WINDOWS = os.name == 'nt'
if _IS_WINDOWS:
    try:
        import ctypes
        import win32gui
        ...
    except ImportError:
        _IS_WINDOWS = False
```

受影响文件：`window_control.py`, `screen_pen.py`, `snipping_tool.py`, `image_window.py`, `main.py`

### 1.3 NSScreen 坐标系转换

macOS 的 NSScreen 坐标系是 **左下角为原点**，tkinter 是 **左上角为原点**。转换公式：

```python
y_tkinter = main_screen_height - (frame.origin.y + frame.size.height)
```

**大坑**：最初版本将 NSScreen 返回的 points 乘以 `backingScaleFactor`（Retina 2x），导致 overlay 尺寸翻倍、截图坐标偏移。最终修正为直接使用 point 值。

---

## 2. pynput 热键系统（最大的坑）

热键是整个移植中最棘手的部分，遇到了 **四个独立的问题**，而且互相叠加：

### 2.1 TIS API 主线程崩溃 (SIGTRAP)

**现象**：程序启动后随机 SIGTRAP 崩溃，无有用错误信息。

**根因**：macOS 26.x (Tahoe) 要求 TIS (Text Input Services) API 必须在主线程调用。pynput 的 `keyboard.Listener` 在后台线程创建时会调用 `keycode_context()`（内部使用 TIS），触发 SIGTRAP。

**解决**：在主线程预计算并缓存 `keycode_context`，替换 pynput 内部函数：

```python
# main.py - SnipasteApp.__init__ 中最早期调用
@staticmethod
def _patch_pynput_darwin():
    import pynput._util.darwin as _pynput_darwin
    with _pynput_darwin.keycode_context() as ctx:
        _cached = ctx
    @contextlib.contextmanager
    def _cached_keycode_context():
        yield _cached
    _pynput_darwin.keycode_context = _cached_keycode_context
    # 同样 patch keyboard._darwin 模块
```

### 2.2 GlobalHotKeys 媒体键崩溃 (TypeError)

**现象**：按任意媒体键（亮度、音量、Mission Control）后整个热键线程崩溃，所有热键失效。

**根因**：pynput 1.8.1 的 bug。`_handle_message()` 对 `NSSystemDefined` 事件调用 `on_press(key)` 只传1个参数，但 `GlobalHotKeys._on_press(self, key, injected)` 需要2个参数 → `TypeError: missing 1 required positional argument: 'injected'`。

**解决**：放弃 `GlobalHotKeys`，改用 `Listener` + 手动 `HotKey` 对象：

```python
# screen_pen.py
hk_toggle = HotKey(HotKey.parse(combo), callback)
listener = Listener(on_press=lambda k: hk_toggle.press(_canonical(k)),
                    on_release=lambda k: hk_toggle.release(_canonical(k)))
```

受影响文件：`screen_pen.py`, `window_control.py`, `image_window.py`

### 2.3 F 键映射错乱（F4 触发 F12 的功能）

**现象**：`Shift+F1` 无反应，`Shift+F4` 触发了 `Shift+F12` 对应的功能。

**根因**：macOS 的 F1-F12 默认是媒体键（亮度、Mission Control、Launchpad 等），按 `Shift+F4` 实际发送的是 `Shift+Launchpad`，其 VK code 与标准 F 键完全不同。即使关闭了"使用 F1-F12 作为标准功能键"，在某些键盘上仍然不可靠。

**解决**：放弃 F 键热键，macOS 默认使用 `Ctrl+Shift+数字键`：

```python
# main.py
'hotkey_toggle_visibility': '<ctrl>+<shift>+1' if sys.platform == 'darwin' else '<shift>+<f1>',
'hotkey_quick_notes':       '<ctrl>+<shift>+7' if sys.platform == 'darwin' else '<shift>+<f7>',
...
```

### 2.4 Shift 组合键字符不匹配

**现象**：`Ctrl+Shift+4` 无法触发，debug 显示 pynput 收到的是 `$` 而非 `4`。

**根因**：macOS 上按 `Shift+4` 时，pynput 收到 `KeyCode(char='$', vk=21)`。但 `HotKey.parse('<ctrl>+<shift>+4')` 期望匹配 `KeyCode.from_char('4')`。字符不匹配导致热键永远不触发。

**解决**：构建 VK code → 未修饰字符 的映射表，使用 pynput 内部的 `SYMBOLS` 表：

```python
# window_control.py - HotkeyListener.__init__
self._vk_to_char = {}
if sys.platform == 'darwin':
    from pynput._util.darwin_vks import SYMBOLS
    for vk, ch in SYMBOLS.items():
        if ch.isprintable():
            self._vk_to_char[vk] = ch.lower()

def _canonical(self, key):
    if isinstance(key, KeyCode):
        # 优先通过 VK 查找未修饰字符
        if key.vk is not None and key.vk in self._vk_to_char:
            return KeyCode.from_char(self._vk_to_char[key.vk])
        ...
```

---

## 3. 截图引擎 (SnippingTool)

### 3.1 Overlay 残影 / 蓝色遮罩混入截图

**现象**：截出的图有蓝色半透明遮罩效果。

**根因**：`overlay.withdraw()` 在 macOS 上是异步的，窗口服务器还没完全隐藏 overlay 时 `mss.grab()` 就开始截图了。

**解决**：

```python
for overlay in self.overlays:
    overlay.withdraw()
self.root.update_idletasks()
self.root.update()
if _IS_MAC:
    time.sleep(0.15)  # 等待窗口服务器完成
```

### 3.2 截图模糊（Retina 坐标不匹配）

**现象**：截图比系统截图模糊。

**根因**：tkinter 的 `event.x_root` 返回 **points**（逻辑像素），但 `mss` 使用 **物理像素**。在 2x Retina 屏上，截图区域只有实际的一半大小，然后被拉伸显示。

**解决**：截图坐标乘以 Retina scale factor：

```python
scale = NSScreen.mainScreen().backingScaleFactor()  # 通常为 2.0
monitor = {
    "top": int(y1 * scale),
    "left": int(x1 * scale),
    "width": int((x2 - x1) * scale),
    "height": int((y2 - y1) * scale)
}
```

### 3.3 选区红边混入截图

**现象**：截图左侧和上侧有 1px 红线。

**根因**：选区矩形 `outline='red'` 是画在 overlay canvas 上的。如果 overlay 没完全隐藏就截图，红线就会被捕获。3.1 的修复同时解决了此问题。

---

## 4. UI / Tkinter 兼容性

### 4.1 macOS 上 tk.Button 不显示文字

**现象**：Image Gallery 底部按钮全部空白，看不到文字。

**根因**：macOS Aqua 主题的 `tk.Button` 忽略 `fg` 和 `bg` 参数，文字用系统默认颜色渲染（深色），在深色背景上不可见。

**解决**：macOS 使用 `ttk.Button` + 自定义 Style：

```python
if _is_mac:
    style = ttk.Style()
    style.configure(style_name, background=bg, foreground=fg, ...)
    btn = ttk.Button(parent, text=text, style=style_name)
else:
    btn = tk.Button(parent, bg=bg, fg=fg, ...)
```

### 4.2 Quick Notes 窗口全黑 / 组件缺失

**现象**：`Ctrl+Shift+7` 打开的 Quick Notes 窗口完全空白。

**根因**：三个叠加问题：

1. **`StringVar.trace("w", ...)` 已废弃**：Python 3.12 + Tcl 9.x 移除了 `trace variable` 命令，改为 `trace add`。调用 `search_var.trace("w", callback)` 直接抛 `TclError: bad option "variable"`, 导致 `_create_ui()` 中断，所有 UI 组件都没创建。
   - **修复**：`trace("w", ...)` → `trace_add("write", ...)`

2. **窗口存在但 UI 组件为空**：第一次创建失败后，`self.window` 已赋值（`CTkToplevel` 已创建），后续调用 `show_window()` 检测到 window 存在就直接 lift，但 `notes_tree` 等组件全是 `None`。
   - **修复**：添加 UI 完整性检查 —— 如果 window 存在但 `notes_tree` 为 None，销毁重建。

3. **`CTkToplevel()` 无 parent**：macOS 上不传 parent 会导致渲染问题。
   - **修复**：`CTkToplevel(app.root)` + `update_idletasks()`

### 4.3 `_clear_editor` 代码损坏

**现象**：Quick Notes 编辑器清空时崩溃。

**根因**：`quick_notes_ui.py` 第 958 行代码合并损坏：`self.current_note_id = Nonelf.editor_text.delete(...)` — `None` 和 `self` 粘在了一起，后面还有重复行。

**修复**：手动修正为正确的两行代码。

### 4.4 "Missing required field: id" 误报

**现象**：打开 Quick Notes 时终端大量报 `Missing required field: id`。

**根因**：`notes_manager._load_notes_from_local_files()` 用 `*.json` 通配符加载 `~/.fastshot/quicknotes/` 目录，把 `cache_info.json`、`overall_notes_index.json` 等元数据文件当成笔记文件去验证。

**修复**：添加排除集合：

```python
excluded_files = {"cache_info.json", "search_history.json",
                  "cache_lock", "overall_notes_index.json"}
note_files = [f for f in self.notes_dir.glob("*.json")
              if f.name not in excluded_files]
```

### 4.5 ImageWindow 不能 Always on Top

**现象**：截图窗口被其他 app 窗口遮盖。

**根因**：macOS 上 `tk.Toplevel.attributes('-topmost', True)` 只在 tkinter 窗口之间有效。切换到其他 app 后，该窗口会被压到下面。

**解决**：使用 AppKit 的 `NSFloatingWindowLevel`：

```python
from AppKit import NSApp, NSFloatingWindowLevel
for ns_window in NSApp.windows():
    # 匹配到对应窗口后
    ns_window.setLevel_(NSFloatingWindowLevel)
```

---

## 5. GenAI 集成

### 5.1 空 URL 导致崩溃

**现象**：在 Ask 窗口输入问题后线程崩溃：`MissingSchema: Invalid URL ''`

**根因**：`config.ini` 的 `[GenAI]` section 所有 URL 为空，`gpt4o.py` 直接用空字符串发 HTTP 请求。

**解决**：
- `ask()` 函数添加配置检测，`[GenAI]` 未配置时自动 fallback 到 `[PowerGenAI]`
- `get_token()` 和 `check_health()` 添加 URL 空值 guard
- `ask_dialog.py` 的 `ask_dummy()` 添加 try/except，错误信息显示在聊天 UI 中而非崩溃

### 5.2 PowerGenAI Fallback

新增 `_ask_power()` 函数，使用 `[PowerGenAI]` 配置（OpenRouter 兼容）作为后备：

```python
def _ask_power(msgs):
    response = requests.post(
        f"{_power_base_url}/chat/completions",
        headers={'Authorization': f'Bearer {_power_key}'},
        json={"model": _power_model, "messages": msgs, ...}
    )
```

---

## 6. 插件系统 & 工具

### 6.1 插件中的 Windows 依赖

`plugin_hyder.py`, `plugin_mini.py`, `plugin_retriver.py` 中的 `ctypes`、`win32gui` 调用全部条件化处理。

### 6.2 hyder.py 加密工具

文件加密模块中的路径处理从 Windows 反斜杠适配为 `pathlib.Path` 跨平台路径。

### 6.3 OCR 模块

`plugin_ocr.py` 已迁移到 RapidOCR (PP-OCRv5)，本身跨平台兼容，但依赖安装路径做了调整。

---

## 7. 踩坑一览表

| # | 问题 | 严重度 | 根因分类 | 影响范围 |
|---|------|--------|---------|---------|
| 1 | SIGTRAP 崩溃 | 致命 | macOS 线程模型 | 启动即崩 |
| 2 | GlobalHotKeys TypeError | 致命 | pynput bug | 媒体键后所有热键失效 |
| 3 | F 键映射错乱 | 高 | macOS 媒体键 | Shift+F1~F12 全部不工作 |
| 4 | Shift 字符不匹配 | 高 | macOS 键盘布局 | Ctrl+Shift+数字 不触发 |
| 5 | 截图有遮罩残影 | 高 | 异步窗口隐藏 | 截图质量 |
| 6 | 截图模糊 | 高 | Retina 坐标系 | 截图质量 |
| 7 | Button 文字不显示 | 中 | Aqua 主题限制 | Gallery UI |
| 8 | Quick Notes 全黑 | 高 | Tcl 9.x API 变更 | Quick Notes 不可用 |
| 9 | ImageWindow 不置顶 | 中 | macOS 窗口层级 | 使用体验 |
| 10 | AI 对话崩溃 | 中 | 配置未设置 | Ask 功能不可用 |
| 11 | Win32 import 崩溃 | 致命 | 平台差异 | 启动即崩 |
| 12 | `_clear_editor` 代码损坏 | 中 | 代码合并错误 | Quick Notes 编辑 |
| 13 | cache JSON 被误认为笔记 | 低 | 通配符过宽 | 日志噪音 |

---

## 8. 未来注意事项

### 开发守则

1. **永远不要直接 import win32 模块** —— 所有 Windows 专有 import 必须在 `_IS_WINDOWS` 检查内
2. **pynput 热键务必使用 Listener + HotKey 模式** —— 不要使用 `GlobalHotKeys`（pynput 1.8.1 有 bug）
3. **tkinter 坐标是 points（逻辑像素）** —— 与 mss 物理像素不同，涉及截图时必须乘以 scale factor
4. **不要用 `tk.Button` 自定义颜色** —— macOS Aqua 会忽略，用 `ttk.Button` + Style
5. **`StringVar.trace()` 已废弃** —— 使用 `trace_add("write", ...)` 代替 `trace("w", ...)`
6. **`CTkToplevel` 必须传 parent** —— macOS 上不传会导致渲染问题
7. **`overlay.withdraw()` 是异步的** —— 截图前必须 sleep 等待窗口服务器

### 已知待优化项

- [ ] 多显示器截图时第二屏 overlay 覆盖测试（目前 Retina + 外接屏的混合场景未充分测试）
- [ ] Screen Pen 在 macOS 上的性能验证（透明 overlay 绘制）
- [ ] `NSFloatingWindowLevel` 的 ImageWindow 匹配逻辑可改为用 `NSView` ID 精确匹配
- [ ] 考虑用 `pyobjc` 原生截图 API (`CGWindowListCreateImage`) 替代 `mss`，可能获得更好的 Retina 支持
