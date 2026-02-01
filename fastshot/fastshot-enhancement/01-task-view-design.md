# Fastshot Task View & SiyuanWrapper 集成设计文档

## 1. 概述

### 1.1 目标

为 Fastshot 添加两个核心功能：

1. **Task View（任务视图）**：类似 Windows `Win+Tab` 的全屏缩略图视图，展示所有 Image Window
2. **SiyuanWrapper 集成**：选中的图片可以打包成 Session，加密后发送到 SiyuanWrapper API 同步到思源笔记

### 1.2 用户场景

```
用户工作流程:
1. 用户在工作中使用 Fastshot 截取多张截图（10-20张）
2. 按下快捷键（如 Ctrl+Tab）打开 Task View
3. 全屏显示所有截图的缩略图，平铺排列
4. 用户框选/多选需要同步的截图
5. 点击底部工具栏的"同步到思源"按钮
6. 系统自动打包、加密、发送到 SiyuanWrapper
7. 思源笔记中自动创建带有这些截图的文档
```

### 1.3 设计原则

- **非侵入式**：新功能作为独立模块，不修改现有核心代码
- **一致性**：UI 风格与现有 Fastshot 保持一致（深色主题）
- **高性能**：大量窗口时保持流畅（50+ 窗口）
- **可配置**：快捷键、API 地址等可通过配置文件设置

---

## 2. 系统架构

### 2.1 模块架构

```
fastshot/
├── task_view/                      # 新增模块
│   ├── __init__.py
│   ├── task_view_overlay.py        # 全屏 Task View 覆盖层
│   ├── thumbnail_grid.py           # 缩略图网格组件
│   ├── selection_manager.py        # 多选管理器
│   ├── toolbar.py                  # 底部工具栏
│   └── animations.py               # 过渡动画
│
├── siyuan_sync/                    # 新增模块
│   ├── __init__.py
│   ├── sync_manager.py             # 同步管理器
│   ├── session_builder.py          # Session 构建器
│   ├── api_client.py               # SiyuanWrapper API 客户端
│   └── sync_progress_dialog.py     # 同步进度对话框
│
├── main.py                         # 修改：注册新快捷键
├── config.ini                      # 修改：添加新配置项
└── window_control.py               # 修改：添加快捷键回调
```

### 2.2 类图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              TASK VIEW MODULE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐      │
│  │  TaskViewOverlay │    │  ThumbnailGrid   │    │ SelectionManager │      │
│  │                  │    │                  │    │                  │      │
│  │ - root: Toplevel │───>│ - thumbnails[]   │───>│ - selected_ids   │      │
│  │ - grid: ...      │    │ - columns: int   │    │ - drag_start     │      │
│  │ - toolbar: ...   │    │ - spacing: int   │    │ - drag_rect      │      │
│  │                  │    │                  │    │                  │      │
│  │ + show()         │    │ + render()       │    │ + toggle(id)     │      │
│  │ + hide()         │    │ + on_click()     │    │ + select_range() │      │
│  │ + on_escape()    │    │ + on_hover()     │    │ + clear()        │      │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘      │
│           │                                               │                 │
│           │              ┌──────────────────┐             │                 │
│           └─────────────>│     Toolbar      │<────────────┘                 │
│                          │                  │                               │
│                          │ - sync_btn       │                               │
│                          │ - select_all_btn │                               │
│                          │ - cancel_btn     │                               │
│                          │ - status_label   │                               │
│                          │                  │                               │
│                          │ + on_sync_click()│                               │
│                          └──────────────────┘                               │
│                                   │                                         │
└───────────────────────────────────┼─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            SIYUAN SYNC MODULE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐      │
│  │   SyncManager    │    │  SessionBuilder  │    │    APIClient     │      │
│  │                  │    │                  │    │                  │      │
│  │ - api_client     │───>│ - windows[]      │    │ - base_url       │      │
│  │ - session_builder│    │ - metadata       │    │ - encryption_key │      │
│  │ - encryption_key │    │                  │    │                  │      │
│  │                  │    │ + build()        │    │ + upload_session │      │
│  │ + sync_windows() │    │ + to_json()      │    │ + health_check() │      │
│  │ + on_complete()  │    │ + encrypt()      │    │                  │      │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Task View 设计

### 3.1 UI 布局

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          TASK VIEW (全屏覆盖层)                               │
│  背景: 半透明深色 (rgba(0,0,0,0.85))                                          │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                         缩略图网格区域                                    ││
│  │                                                                          ││
│  │   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐                ││
│  │   │ [1] ✓   │   │ [2]     │   │ [3] ✓   │   │ [4]     │                ││
│  │   │         │   │         │   │         │   │         │                ││
│  │   │  截图1   │   │  截图2   │   │  截图3   │   │  截图4   │                ││
│  │   │         │   │         │   │         │   │         │                ││
│  │   └─────────┘   └─────────┘   └─────────┘   └─────────┘                ││
│  │                                                                          ││
│  │   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐                ││
│  │   │ [5]     │   │ [6] ✓   │   │ [7]     │   │ [8]     │                ││
│  │   │         │   │         │   │         │   │         │                ││
│  │   │  截图5   │   │  截图6   │   │  截图7   │   │  截图8   │                ││
│  │   │         │   │         │   │         │   │         │                ││
│  │   └─────────┘   └─────────┘   └─────────┘   └─────────┘                ││
│  │                                                                          ││
│  │                        [ 可滚动，支持鼠标滚轮 ]                            ││
│  │                                                                          ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                            底部工具栏                                     ││
│  │                                                                          ││
│  │   已选择: 3 张    [全选]  [取消选择]  |  [同步到思源 ▶]  |  [ESC 关闭]    ││
│  │                                                                          ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 缩略图卡片设计

```
┌─────────────────────────────────────┐
│  [序号]                    [✓ 选中] │  ← 顶部信息栏 (半透明黑色背景)
├─────────────────────────────────────┤
│                                     │
│                                     │
│           缩略图图片                 │  ← 保持宽高比，居中显示
│         (200x150 左右)              │
│                                     │
│                                     │
├─────────────────────────────────────┤
│  截图时间: 14:32:05                  │  ← 底部信息栏
└─────────────────────────────────────┘

状态样式:
- 普通: 边框 #444, 背景 #2a2a2a
- 悬停: 边框 #666, 背景 #3a3a3a, 轻微放大 (scale 1.02)
- 选中: 边框 #4a9eff (蓝色), 背景 #1a3a5a, 显示勾选图标
- 选中+悬停: 边框 #6ab4ff, 背景 #2a4a6a
```

### 3.3 交互设计

#### 3.3.1 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+Tab` | 打开 Task View |
| `ESC` | 关闭 Task View |
| `Ctrl+A` | 全选所有缩略图 |
| `Enter` | 同步选中的图片 |
| `1-9` | 快速选中/取消选中对应序号 |
| `↑↓←→` | 键盘导航 |
| `Space` | 选中/取消当前焦点项 |

#### 3.3.2 鼠标交互

| 操作 | 效果 |
|------|------|
| 单击缩略图 | 切换选中状态 |
| Ctrl+单击 | 添加到选择（多选） |
| Shift+单击 | 范围选择（从上次点击到当前） |
| 拖拽空白区域 | 框选多个缩略图 |
| 双击缩略图 | 关闭 Task View，聚焦该窗口 |
| 滚轮 | 上下滚动 |
| 右键缩略图 | 上下文菜单（删除、隐藏等） |

#### 3.3.3 框选实现

```python
class SelectionManager:
    def on_mouse_down(self, event):
        """开始框选"""
        self.drag_start = (event.x, event.y)
        self.is_dragging = True
        self.selection_rect = None

    def on_mouse_move(self, event):
        """更新框选矩形"""
        if self.is_dragging:
            x1, y1 = self.drag_start
            x2, y2 = event.x, event.y
            self.selection_rect = (min(x1,x2), min(y1,y2),
                                   max(x1,x2), max(y1,y2))
            self.update_preview_selection()

    def on_mouse_up(self, event):
        """完成框选，确认选中"""
        if self.selection_rect:
            self.confirm_selection()
        self.is_dragging = False
```

### 3.4 动画效果

| 动画 | 时长 | 效果 |
|------|------|------|
| 打开 Task View | 200ms | 从当前窗口位置缩放到全屏 + 淡入 |
| 关闭 Task View | 150ms | 淡出 + 缩放回原位置 |
| 缩略图悬停 | 100ms | scale 1.0 → 1.02，阴影加深 |
| 选中状态切换 | 80ms | 边框颜色渐变，勾选图标淡入 |

---

## 4. SiyuanWrapper 集成设计

### 4.1 配置项

```ini
# config.ini 新增配置

[SiyuanSync]
# 是否启用思源同步功能
enabled = true

# SiyuanWrapper API 地址
api_url = http://localhost:8000

# 加密密钥（与 CloudSync 共用或单独配置）
encryption_key = qwer1234

# 同步后是否自动关闭选中的窗口
close_after_sync = false

# 同步超时时间（秒）
timeout = 30

# 是否显示同步成功通知
show_notification = true
```

### 4.2 API 调用流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SYNC TO SIYUAN FLOW                                  │
└─────────────────────────────────────────────────────────────────────────────┘

User clicks "同步到思源"
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 1: Build Session                                                        │
│                                                                              │
│  selected_windows = selection_manager.get_selected()                         │
│                                                                              │
│  session_data = {                                                            │
│      "session": {                                                            │
│          "version": "1.0",                                                   │
│          "timestamp": "2026-02-02T15:30:00",                                │
│          "windows": [                                                        │
│              {                                                               │
│                  "index": 0,                                                 │
│                  "original_image_data": "base64...",                        │
│                  "draw_history": [...],                                      │
│                  ...                                                         │
│              }                                                               │
│          ]                                                                   │
│      },                                                                      │
│      "metadata": {                                                           │
│          "name": "Quick Sync 2026-02-02 15:30",                             │
│          "desc": "Synced from Fastshot Task View",                          │
│          "tags": ["fastshot", "quick-sync"],                                │
│          "created_at": "...",                                               │
│          "image_count": 3                                                   │
│      }                                                                       │
│  }                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 2: Encrypt Session                                                      │
│                                                                              │
│  # 复用 CloudSyncManager 的加密逻辑                                           │
│  json_data = json.dumps(session_data).encode('utf-8')                        │
│  encrypted = xor_encrypt(json_data, encryption_key)                          │
│                                                                              │
│  # 创建带 FHDR 标记的加密文件                                                  │
│  thumbnail = create_thumbnail_collage(selected_windows)                      │
│  output = thumbnail_png_bytes + b'FHDR' + encrypted                          │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 3: Upload to SiyuanWrapper                                              │
│                                                                              │
│  POST {api_url}/webhook/fastshot/en                                          │
│  Content-Type: multipart/form-data                                           │
│                                                                              │
│  Form Fields:                                                                │
│    - file: (encrypted .fastshot file bytes)                                  │
│    - key: (encryption_key, optional if server has it configured)            │
│                                                                              │
│  Headers:                                                                    │
│    - X-Fastshot-Client: "TaskView/1.0"                                      │
│    - X-Fastshot-Timestamp: "2026-02-02T15:30:00"                            │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 4: Handle Response                                                      │
│                                                                              │
│  Success (200):                                                              │
│  {                                                                           │
│      "status": "ok",                                                         │
│      "session_id": "20260202153000_QuickSync",                              │
│      "images_uploaded": 3,                                                   │
│      "document_created": true,                                               │
│      "doc_id": "20260202153000-abcdef"                                      │
│  }                                                                           │
│  → 显示成功通知                                                               │
│  → 可选: 关闭已同步的窗口                                                      │
│                                                                              │
│  Error (4xx/5xx):                                                            │
│  {                                                                           │
│      "status": "error",                                                      │
│      "detail": "Error message"                                               │
│  }                                                                           │
│  → 显示错误提示                                                               │
│  → 保留窗口状态                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 同步进度对话框

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        同步到思源笔记                                   [X]  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │████████████████████████████░░░░░░░░░░░░░░░░░░░░░░░│ 65%              │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   状态: 正在上传图片 2/3...                                                  │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐ │
│   │ ✓ 构建 Session 数据                                                   │ │
│   │ ✓ 创建缩略图                                                          │ │
│   │ ✓ 加密数据                                                            │ │
│   │ ● 上传到 SiyuanWrapper...                                             │ │
│   │ ○ 等待服务器响应                                                       │ │
│   └──────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│                                              [取消]                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.4 错误处理

| 错误类型 | 处理方式 |
|----------|----------|
| 网络超时 | 显示"连接超时，请检查网络"，提供重试按钮 |
| 连接拒绝 | 显示"无法连接到 SiyuanWrapper，请确认服务已启动" |
| 401 未授权 | 显示"认证失败，请检查 Access Code 配置" |
| 500 服务器错误 | 显示服务器返回的错误信息 |
| 加密失败 | 显示"加密失败"，记录详细日志 |

---

## 5. 代码实现指南

### 5.1 TaskViewOverlay 核心实现

```python
# task_view/task_view_overlay.py

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from typing import List, Optional, Callable
import threading

class TaskViewOverlay:
    """全屏 Task View 覆盖层"""

    def __init__(self, app, windows: List['ImageWindow']):
        self.app = app
        self.windows = windows
        self.root = None
        self.grid = None
        self.toolbar = None
        self.selection_manager = SelectionManager()

    def show(self):
        """显示 Task View"""
        # 创建全屏窗口
        self.root = tk.Toplevel(self.app.root)
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-topmost', True)
        self.root.configure(bg='#1a1a1a')

        # 设置透明度（可选动画）
        self.root.attributes('-alpha', 0.95)

        # 绑定按键
        self.root.bind('<Escape>', self.on_escape)
        self.root.bind('<Control-a>', self.on_select_all)
        self.root.bind('<Return>', self.on_sync)

        # 创建主布局
        self._create_layout()

        # 渲染缩略图
        self._render_thumbnails()

        # 聚焦
        self.root.focus_force()

    def hide(self):
        """隐藏 Task View"""
        if self.root:
            self.root.destroy()
            self.root = None

    def _create_layout(self):
        """创建主布局"""
        # 顶部标题
        header = tk.Frame(self.root, bg='#1a1a1a', height=60)
        header.pack(fill='x', padx=20, pady=10)

        title = tk.Label(header, text="Task View",
                        font=('Segoe UI', 18, 'bold'),
                        fg='white', bg='#1a1a1a')
        title.pack(side='left')

        # 缩略图网格区域（可滚动）
        self.grid_container = tk.Frame(self.root, bg='#1a1a1a')
        self.grid_container.pack(fill='both', expand=True, padx=20)

        # 创建 Canvas + Scrollbar 实现滚动
        self.canvas = tk.Canvas(self.grid_container, bg='#1a1a1a',
                               highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.grid_container,
                                       orient='vertical',
                                       command=self.canvas.yview)

        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scrollbar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)

        # 网格 Frame
        self.grid = tk.Frame(self.canvas, bg='#1a1a1a')
        self.canvas.create_window((0, 0), window=self.grid, anchor='nw')

        # 鼠标滚轮
        self.canvas.bind('<MouseWheel>', self._on_mousewheel)

        # 底部工具栏
        self.toolbar = TaskViewToolbar(self.root, self)
        self.toolbar.pack(fill='x', padx=20, pady=10)

    def _render_thumbnails(self):
        """渲染所有缩略图"""
        # 计算列数（基于屏幕宽度）
        screen_width = self.root.winfo_screenwidth()
        thumb_width = 220  # 缩略图宽度 + padding
        columns = max(4, screen_width // thumb_width)

        for i, window in enumerate(self.windows):
            if window.is_hidden:
                continue

            row = i // columns
            col = i % columns

            card = ThumbnailCard(
                self.grid,
                window=window,
                index=i,
                selection_manager=self.selection_manager,
                on_double_click=self._on_thumbnail_double_click
            )
            card.grid(row=row, column=col, padx=10, pady=10)

        # 更新滚动区域
        self.grid.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def _on_thumbnail_double_click(self, window: 'ImageWindow'):
        """双击缩略图：关闭 Task View，聚焦该窗口"""
        self.hide()
        window.show()
        window.focus()

    def on_escape(self, event=None):
        """ESC 关闭"""
        self.hide()

    def on_select_all(self, event=None):
        """全选"""
        self.selection_manager.select_all(self.windows)
        self._update_selection_ui()

    def on_sync(self, event=None):
        """同步选中项"""
        selected = self.selection_manager.get_selected()
        if not selected:
            return

        self.hide()

        # 启动同步
        from siyuan_sync import SyncManager
        sync_manager = SyncManager(self.app.config)
        sync_manager.sync_windows(selected,
                                  on_complete=self._on_sync_complete,
                                  on_error=self._on_sync_error)
```

### 5.2 SyncManager 核心实现

```python
# siyuan_sync/sync_manager.py

import json
import httpx
import threading
from typing import List, Callable, Optional
from datetime import datetime

class SyncManager:
    """思源同步管理器"""

    def __init__(self, config):
        self.config = config
        self.api_url = config.get('SiyuanSync', 'api_url',
                                  fallback='http://localhost:8000')
        self.encryption_key = config.get('SiyuanSync', 'encryption_key',
                                         fallback='qwer1234')
        self.timeout = config.getint('SiyuanSync', 'timeout', fallback=30)

    def sync_windows(self,
                     windows: List['ImageWindow'],
                     on_progress: Optional[Callable] = None,
                     on_complete: Optional[Callable] = None,
                     on_error: Optional[Callable] = None):
        """异步同步选中的窗口"""

        def _sync_thread():
            try:
                # Step 1: 构建 Session
                if on_progress:
                    on_progress(10, "构建 Session 数据...")

                session_data = self._build_session(windows)

                # Step 2: 加密
                if on_progress:
                    on_progress(30, "加密数据...")

                encrypted_file = self._encrypt_session(session_data)

                # Step 3: 上传
                if on_progress:
                    on_progress(50, "上传到 SiyuanWrapper...")

                result = self._upload_to_siyuan(encrypted_file)

                if on_progress:
                    on_progress(100, "同步完成!")

                if on_complete:
                    on_complete(result)

            except Exception as e:
                if on_error:
                    on_error(str(e))

        thread = threading.Thread(target=_sync_thread, daemon=True)
        thread.start()

    def _build_session(self, windows: List['ImageWindow']) -> dict:
        """构建 Session 数据"""
        timestamp = datetime.now().isoformat()

        session_windows = []
        for i, window in enumerate(windows):
            session_windows.append({
                "index": i,
                "geometry": {
                    "x": window.img_window.winfo_x(),
                    "y": window.img_window.winfo_y(),
                    "width": window.img_window.winfo_width(),
                    "height": window.img_window.winfo_height()
                },
                "scale": getattr(window.img_label, 'scale', 1.0),
                "image_data": self._serialize_image(
                    window.img_label.zoomed_image
                ),
                "original_image_data": self._serialize_image(
                    window.img_label.original_image
                ),
                "draw_history": getattr(window, 'draw_history', []),
                "is_hidden": window.is_hidden,
                "window_id": id(window)
            })

        return {
            "session": {
                "version": "1.0",
                "timestamp": timestamp,
                "windows": session_windows
            },
            "metadata": {
                "name": f"Quick Sync {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                "desc": "Synced from Fastshot Task View",
                "tags": ["fastshot", "quick-sync"],
                "color": "blue",
                "class": "",
                "created_at": timestamp,
                "image_count": len(windows)
            }
        }

    def _encrypt_session(self, session_data: dict) -> bytes:
        """加密 Session 数据"""
        # 复用现有加密逻辑
        from plugins.utils.hyder import xor_encrypt

        json_bytes = json.dumps(session_data).encode('utf-8')
        encrypted = xor_encrypt(json_bytes, self.encryption_key)

        # 创建缩略图作为载体
        thumbnail = self._create_thumbnail(session_data)
        thumbnail_bytes = self._image_to_bytes(thumbnail)

        # 组合: PNG + FHDR + 加密数据
        return thumbnail_bytes + b'FHDR' + encrypted

    def _upload_to_siyuan(self, encrypted_file: bytes) -> dict:
        """上传到 SiyuanWrapper"""
        url = f"{self.api_url}/webhook/fastshot/en"

        files = {
            'file': ('session.fastshot', encrypted_file, 'image/png')
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, files=files)
            response.raise_for_status()
            return response.json()
```

### 5.3 快捷键注册

```python
# main.py 修改

class SnipasteApp:
    def __init__(self):
        # ... 现有初始化代码 ...

        # 初始化 Task View
        self.task_view = None

    def load_hotkeys(self):
        # ... 现有快捷键 ...

        # 新增 Task View 快捷键
        self.hotkeys['task_view'] = keyboard.HotKey(
            keyboard.HotKey.parse('<ctrl>+<tab>'),
            self.on_task_view
        )

    def on_task_view(self):
        """打开 Task View"""
        if not self.windows:
            return

        if self.task_view and self.task_view.is_visible():
            self.task_view.hide()
        else:
            from task_view import TaskViewOverlay
            self.task_view = TaskViewOverlay(self, self.windows)
            self.task_view.show()
```

---

## 6. 配置文件更新

### 6.1 config.ini 新增配置

```ini
# 在 config.ini 末尾添加

[SiyuanSync]
# 是否启用思源同步
enabled = true

# SiyuanWrapper API 地址
api_url = http://localhost:8000

# 加密密钥（用于加密同步数据）
encryption_key = qwer1234

# 同步后是否关闭已同步的窗口
close_after_sync = false

# 同步超时（秒）
timeout = 30

# 同步成功后显示通知
show_notification = true

# 默认 Session 名称前缀
default_name_prefix = Quick Sync

# 默认标签（逗号分隔）
default_tags = fastshot,quick-sync

[TaskView]
# Task View 快捷键
hotkey = <ctrl>+<tab>

# 缩略图尺寸
thumbnail_width = 200
thumbnail_height = 150

# 动画时长（毫秒）
animation_duration = 200

# 背景透明度 (0.0 - 1.0)
background_opacity = 0.9
```

---

## 7. 测试计划

### 7.1 单元测试

| 测试项 | 测试内容 |
|--------|----------|
| SessionBuilder | 验证 Session JSON 结构正确性 |
| 加密/解密 | 验证 XOR 加密与 SiyuanWrapper 解密兼容 |
| ThumbnailCreator | 验证缩略图生成正确 |
| SelectionManager | 验证单选、多选、框选逻辑 |

### 7.2 集成测试

| 测试项 | 测试内容 |
|--------|----------|
| API 调用 | 验证与 SiyuanWrapper `/webhook/fastshot/en` 的兼容性 |
| 端到端同步 | 从 Task View 选择 → 同步 → 思源文档创建 |
| 错误恢复 | 网络中断、服务器错误时的用户提示 |

### 7.3 性能测试

| 测试项 | 目标 |
|--------|------|
| Task View 打开 | < 200ms（50 个窗口） |
| 缩略图渲染 | < 500ms（50 个缩略图） |
| 同步上传 | < 5s（10 张图片，1MB 总大小） |
| 内存占用 | Task View 打开时 < +100MB |

---

## 8. 实现计划

### Phase 1: Task View 基础功能（3-4天）

1. 创建 `task_view/` 模块结构
2. 实现 TaskViewOverlay 全屏覆盖层
3. 实现 ThumbnailCard 缩略图卡片
4. 实现基本的单击选择
5. 实现键盘导航（方向键、ESC）
6. 添加快捷键 Ctrl+Tab

### Phase 2: 多选与交互增强（2-3天）

1. 实现 SelectionManager 多选逻辑
2. 实现 Ctrl+Click 多选
3. 实现 Shift+Click 范围选择
4. 实现鼠标框选
5. 实现工具栏（全选、取消选择）

### Phase 3: SiyuanWrapper 集成（2-3天）

1. 创建 `siyuan_sync/` 模块
2. 实现 SessionBuilder
3. 实现 APIClient（复用加密逻辑）
4. 实现 SyncProgressDialog
5. 实现错误处理和重试

### Phase 4: 优化与测试（2天）

1. 添加动画效果
2. 性能优化（大量窗口）
3. 编写测试用例
4. 文档更新

**总计预估工时：9-12天**

---

## 9. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Tkinter 性能瓶颈 | 50+ 窗口时卡顿 | 使用虚拟化（只渲染可见项） |
| 跨平台兼容性 | Windows/Mac 差异 | 分平台测试，条件判断 |
| SiyuanWrapper 不可用 | 同步失败 | 健康检查 + 友好错误提示 |
| 内存泄漏 | 长时间运行卡顿 | Task View 关闭时彻底清理 |

---

## 10. 未来扩展

1. **Session 预览**：Task View 中可预览完整 Session（非仅单张图）
2. **拖拽排序**：在 Task View 中拖拽调整图片顺序
3. **快速编辑**：Task View 中直接添加标签、描述
4. **批量操作**：删除、导出选中的图片
5. **搜索过滤**：按时间、标签筛选缩略图
6. **云端历史**：查看已同步到思源的历史记录

---

*文档版本: 1.0*
*创建日期: 2026-02-02*
*作者: Claude (AI Assistant)*
