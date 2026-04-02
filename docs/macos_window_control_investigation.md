# macOS Window Control Investigation — Always-on-Top & Opacity

## Background

Fastshot on Windows uses Win32 API (`SetWindowPos`, `SetLayeredWindowAttributes`) to control **any** foreground window's always-on-top state and opacity. Porting to macOS required finding equivalent system-wide window control mechanisms.

**Environment**: Python 3.12.13, macOS Sequoia (Darwin 25.2.0), pyobjc available

---

## Approaches Tested

### 1. CGS Private API — `CGSSetWindowAlpha`

```python
cg = ctypes.cdll.LoadLibrary(ctypes.util.find_library('CoreGraphics'))
conn = cg.CGSMainConnectionID()
cg.CGSSetWindowAlpha(conn, window_id, 0.5)
```

| Item | Result |
|------|--------|
| Return code | `0` (success) |
| Visual effect | **None** — window remains fully opaque |

### 2. CGS Private API — `CGSSetWindowOpacity` + `CGSSetWindowAlpha`

先将窗口标记为 non-opaque，再设 alpha：

```python
cg.CGSSetWindowOpacity(conn, window_id, False)
cg.CGSSetWindowAlpha(conn, window_id, 0.5)
```

| Item | Result |
|------|--------|
| Return codes | Both `0` |
| Visual effect | **None** |

### 3. CGS Private API — `CGSSetWindowLevel`

```python
cg.CGSSetWindowLevel(conn, window_id, 3)  # kCGFloatingWindowLevel
```

| Item | Result |
|------|--------|
| Return code | `0` |
| Visual effect | **None** — window does not stay on top |

### 4. CGS Private API — `CGSSetWindowLevel` + `CGSOrderWindow`

设 level 后强制重排窗口栈：

```python
cg.CGSSetWindowLevel(conn, window_id, level)
cg.CGSOrderWindow(conn, window_id, 1, 0)  # kCGSOrderAbove, above all
```

| Level | SetLevel result | OrderWindow result | Visual effect |
|-------|----------------|-------------------|---------------|
| 3 (Floating) | `0` | **`1000`** (permission denied) | None |
| 8 (ModalPanel) | `0` | **`1000`** | None |
| 25 (StatusWindow) | `0` | **`1000`** | None |
| 1000 (ScreenSaver) | `0` | **`1000`** | None |

`CGSOrderWindow` 在所有 level 下均返回 **1000（权限拒绝）**。

### 5. Accessibility API (AXUIElement)

```python
from ApplicationServices import AXUIElementCreateApplication, AXIsProcessTrusted
```

| Item | Result |
|------|--------|
| `AXIsProcessTrusted()` | `True` (已授权) |
| 读取 AXWindows, AXTitle, AXPosition, AXSize | 正常工作 |
| `AXRaise` action | 返回 `0`，可将窗口提到前台 |
| 设置 opacity | **无此属性** |
| 设置 window level | **无此属性** |

Accessibility API 只能读取窗口属性和执行有限操作（Raise, Minimize），**不支持设置透明度或窗口层级**。

### 6. AppleScript (System Events)

```applescript
tell application "System Events"
    set targetApp to first application process whose frontmost is true
end tell
```

- 可以获取前台应用信息
- **无 opacity 或 window level 控制能力**

---

## Root Cause

**macOS Sequoia (15.x) 已封锁 CGS 私有 API 对第三方进程窗口的控制。**

- `CGSSetWindowAlpha` / `CGSSetWindowLevel`：API 调用返回成功（`0`），但 WindowServer 静默忽略，不产生任何视觉效果
- `CGSOrderWindow`：直接返回错误码 `1000`（权限拒绝）
- 这些 API 仅对 **当前进程自身的窗口** 生效，无法跨进程控制

这是 Apple 从 macOS Catalina 开始逐步收紧、在 Sequoia 上彻底封锁的安全策略。工具如 [yabai](https://github.com/koekeishiya/yabai) 通过注入 scripting addition 到 WindowServer 进程来绕过此限制，但需要 **部分禁用 SIP (System Integrity Protection)**。

---

## Final Conclusion

| 功能 | Windows | macOS (Fastshot 自身窗口) | macOS (任意应用窗口) |
|------|---------|--------------------------|---------------------|
| Always-on-top toggle | Win32 `SetWindowPos` | tkinter `attributes('-topmost')` | **不可能** (无 SIP 修改) |
| Opacity 调节 | Win32 `SetLayeredWindowAttributes` | tkinter `attributes('-alpha')` | **不可能** (无 SIP 修改) |

### 当前实现

- **Fastshot ImageWindow**：热键可用，通过鼠标位置检测当前窗口，直接调用 tkinter API
- **任意第三方窗口**：macOS 系统限制，无法实现

### 如需系统级窗口控制

需安装 yabai 并按其文档配置：

1. 部分禁用 SIP：`csrutil enable --without fs --without debug --without nvram`
2. 安装 yabai：`brew install koekeishiya/formulae/yabai`
3. 安装 scripting addition：`sudo yabai --install-sa`
4. 通过 yabai CLI 控制：`yabai -m window --opacity 0.5` / `yabai -m window --layer above`

这超出 Fastshot 应用层面的能力范围。
