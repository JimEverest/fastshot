import tkinter as tk
from tkinter import ttk


class CalendarSyncFrame(ttk.Frame):
    """Settings tab "Outlook Calendar": automatic sending on/off, how often, which days, and 立即同步 with progress."""

    def __init__(self, parent, settings_manager, app=None):
        super().__init__(parent)
        self.settings_manager, self.app = settings_manager, app
        self.create_widgets()

    def create_widgets(self):
        settings = self.settings_manager.get_section('CalendarSync')

        row = ttk.Frame(self)
        row.pack(fill='x', padx=10, pady=(10, 5))
        self.enabled_var = tk.BooleanVar(value=str(settings.get('enabled', 'False')).lower() == 'true')
        ttk.Checkbutton(row, text="自动同步 Outlook 日历到 Life OS（Enable automatic sync）",
                        variable=self.enabled_var).pack(side='left')

        self.interval_var = self._spin("每隔几分钟同步一次 / Interval (minutes):", settings.get('interval_minutes', '15'), 5, 240)
        self.back_var = self._spin("往前同步几天 / Days back:", settings.get('days_back', '1'), 0, 30)
        self.ahead_var = self._spin("往后同步几天 / Days ahead:", settings.get('days_ahead', '14'), 1, 60)

        now = ttk.Frame(self)
        now.pack(fill='x', padx=10, pady=(12, 5))
        self.sync_btn = ttk.Button(now, text="立即同步 / Sync now", command=self.sync_now)
        self.sync_btn.pack(side='left')
        hotkey = self.settings_manager.get_section('Shortcuts').get('hotkey_calendar_sync', '<shift>+<f9>')
        ttk.Label(now, text=f"  也可以随时按 {hotkey} 手动同步（右下角会提示进度）", foreground='gray').pack(side='left')

        self.status_var = tk.StringVar(value=self._status())
        ttk.Label(self, textvariable=self.status_var, justify='left', wraplength=520).pack(padx=10, pady=8, anchor='w')

        help_text = (
            "说明 / Note:\n"
            "1. 只支持经典版桌面 Outlook（不支持 New Outlook），在本机直接读取，不需要 ICS 或 Graph 权限。\n"
            "2. 每次发送窗口内的全部日程（时间、主题、地点、组织者、参会人），从不发送会议正文；\n"
            "   私人约会只发送时间，标题显示为「私人安排」。\n"
            "3. 走 Notes Sync 同一个 /ingest、同一个 XOR + PNG 信封和 API Key（先在 Notes Sync 页填好）。\n"
            "4. Life OS 把每次发送当作这段时间的完整日历：Outlook 里删掉的会，在 Life OS 里会标为已取消。\n"
            "5. 关掉自动同步后，只有点「立即同步」或按快捷键时才会同步。"
        )
        ttk.Label(self, text=help_text, justify='left', foreground='gray').pack(padx=10, pady=6, anchor='w')

    def _spin(self, label, value, low, high):
        row = ttk.Frame(self)
        row.pack(fill='x', padx=10, pady=4)
        ttk.Label(row, text=label, width=34).pack(side='left')
        var = tk.StringVar(value=str(value))
        ttk.Spinbox(row, from_=low, to=high, textvariable=var, width=6).pack(side='left', padx=5)
        return var

    def _sync(self):
        return getattr(self.app, 'calendar_sync', None) if self.app is not None else None

    def _status(self):
        sync = self._sync()
        return sync.status_text() if sync is not None else "（Outlook 日历同步在 Fastshot 启动时加载；保存设置后生效）"

    def sync_now(self):
        sync = self._sync()
        if sync is None:
            self.status_var.set("Outlook 日历同步没有启动（请重启 Fastshot）")
            return
        self.sync_btn.state(['disabled'])
        self.status_var.set("开始同步…")

        def progress(stage, text):
            def show():
                if not self.winfo_exists():
                    return
                self.status_var.set(text)
                if stage in ('done', 'error'):
                    self.sync_btn.state(['!disabled'])
            self.after(0, show)
        sync.sync_now(progress=progress)

    def get_settings(self):
        def number(var, default, low, high):
            try:
                return str(max(low, min(high, int(var.get()))))
            except (TypeError, ValueError):
                return str(default)
        return {
            'enabled': str(self.enabled_var.get()),
            'interval_minutes': number(self.interval_var, 15, 5, 240),
            'days_back': number(self.back_var, 1, 0, 30),
            'days_ahead': number(self.ahead_var, 14, 1, 60),
        }
