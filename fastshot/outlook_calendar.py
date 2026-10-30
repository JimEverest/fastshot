# fastshot/outlook_calendar.py
"""Send the desktop Outlook calendar to Life OS, so its morning brief, meeting prep and recordings know the schedule.

Works with classic desktop Outlook on Windows (not the "new Outlook"): it reads the calendar through Outlook's own
COM interface on this machine — no ICS publishing, no Graph permission, no PowerShell. Every `interval_minutes`
it sends the meetings from `days_back` days ago to `days_ahead` days ahead (time, subject, place, organizer,
attendees — never the meeting body) through the same encrypted /ingest envelope NotesSync uses. Life OS treats
each send as the whole calendar for that window: a meeting removed in Outlook is marked cancelled there.

Private appointments (Sensitivity = private) go as "私人安排" with only their time.

config.ini (also on the Settings window's "Outlook Calendar" tab):
    [CalendarSync]
    enabled = True          ; automatic sending; off = only when asked
    interval_minutes = 15
    days_back = 1
    days_ahead = 14
The /ingest address and the two keys come from [NotesSync] (ingest_url, api_key, encryption_key).
Sync by hand any time: Settings → Outlook Calendar → 立即同步, or the hotkey (hotkey_calendar_sync, default Shift+F9),
which shows its progress in a small note in the bottom-right corner.

Try it once from CMD (prints what it read, then sends):
    python -m fastshot.outlook_calendar --once
or only look, without sending:
    python -m fastshot.outlook_calendar --dry-run
"""

import argparse
import configparser
import datetime as dt
import json
import os
import threading
import time
import uuid

OL_FOLDER_CALENDAR = 9
OL_PRIVATE = 2
CANCELLED_STATUSES = (5, 7)          # olMeetingCanceled, olMeetingReceivedAndCanceled
MAX_ITEMS = 3000
MAX_PEOPLE = 12
SOURCE = 'outlook'


def _restrict(items, first, last):
    """Items starting in [first, last). Outlook's Restrict date format depends on the Windows locale, so a few are
    tried; each candidate is checked against the window before it is trusted."""
    formats = ('%m/%d/%Y %I:%M %p', '%m/%d/%Y %H:%M', '%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M')
    for fmt in formats:
        try:
            found = items.Restrict(f"[Start] >= '{first.strftime(fmt)}' AND [Start] < '{last.strftime(fmt)}'")
            item = found.GetFirst()
            if item is None:
                continue
            start = _naive(item.Start)
            if first - dt.timedelta(days=1) <= start <= last + dt.timedelta(days=1):
                return found
        except Exception:
            continue
    return None


def _naive(value):
    """Outlook's local wall-clock time as a naive datetime (pywin32 may label it with a time zone)."""
    return dt.datetime(value.year, value.month, value.day, value.hour, value.minute)


def _people(item):
    names = []
    try:
        for n in range(1, item.Recipients.Count + 1):
            name = str(item.Recipients.Item(n).Name or '').strip()
            if name and name not in names:
                names.append(name)
            if len(names) >= MAX_PEOPLE:
                break
    except Exception:
        pass
    return names


def _event(item):
    start, end = _naive(item.Start), _naive(item.End)
    private = getattr(item, 'Sensitivity', 0) == OL_PRIVATE
    all_day = bool(getattr(item, 'AllDayEvent', False))
    subject = str(item.Subject or '').strip() or '（无主题）'
    try:
        ident = str(item.GlobalAppointmentID or '') or str(item.EntryID or '')
    except Exception:
        ident = ''
    return {
        'id': ident or f"{start:%Y%m%d%H%M}|{subject}",
        'date': start.strftime('%Y-%m-%d'),
        'start': None if all_day else start.strftime('%H:%M'),
        'end': None if all_day else end.strftime('%H:%M'),
        'title': '私人安排' if private else subject,
        'location': None if private else (str(item.Location or '').strip() or None),
        'organizer': None if private else (str(getattr(item, 'Organizer', '') or '').strip() or None),
        'people': [] if private else _people(item),
        'status': 'cancelled' if getattr(item, 'MeetingStatus', 0) in CANCELLED_STATUSES else 'confirmed',
    }


def read_outlook(days_back=1, days_ahead=14, today=None):
    """(window, events) for the default Outlook calendar, recurring meetings expanded into occurrences."""
    import pythoncom
    import win32com.client
    today = today or dt.date.today()
    first = dt.datetime.combine(today - dt.timedelta(days=days_back), dt.time())
    last = dt.datetime.combine(today + dt.timedelta(days=days_ahead + 1), dt.time())
    pythoncom.CoInitialize()
    try:
        namespace = win32com.client.Dispatch('Outlook.Application').GetNamespace('MAPI')
        items = namespace.GetDefaultFolder(OL_FOLDER_CALENDAR).Items
        items.IncludeRecurrences = True
        items.Sort('[Start]')
        found = _restrict(items, first, last) or items   # fall back to walking the sorted calendar
        events, item, seen = [], found.GetFirst(), 0
        while item is not None and seen < MAX_ITEMS:
            seen += 1
            try:
                start = _naive(item.Start)
                if start >= last:
                    break
                if start >= first:
                    events.append(_event(item))
            except Exception as error:  # one odd item must not stop the rest
                print(f"[CalendarSync] skipped an item: {type(error).__name__}")
            item = found.GetNext()
    finally:
        pythoncom.CoUninitialize()
    window = {'from': first.date().isoformat(), 'to': (last.date() - dt.timedelta(days=1)).isoformat()}
    return window, events


def send(notes_sync, window, events):
    """POST the calendar through NotesSync's envelope (XOR + PNG, Bearer api key). Returns Life OS's answer."""
    import requests
    payload = {'source': SOURCE, 'kind': 'calendar', 'client_msg_id': uuid.uuid4().hex, 'window': window,
               'events': events, 'generated_at': dt.datetime.now().isoformat(timespec='seconds')}
    envelope = notes_sync._disguise_in_image(notes_sync._encrypt_data(json.dumps(payload, ensure_ascii=False).encode('utf-8')))
    response = requests.post(notes_sync.ingest_url, files={'file': ('calendar.png', envelope, 'image/png')},
                             headers={'Authorization': f'Bearer {notes_sync.api_key}'}, timeout=60)
    if response.status_code != 200:
        raise RuntimeError(f"Life OS answered {response.status_code}: {response.text[:200]}")
    return response.json()


class OutlookCalendarSync:
    """Automatic sending (when [CalendarSync] enabled = True) and on-demand sending (the Settings tab's 立即同步, or
    the hotkey_calendar_sync hotkey), one at a time. Progress goes to a callback the caller marshals onto the UI
    thread; `last` / `last_error` say how the latest round went."""

    def __init__(self, app):
        self.app = app
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._thread = None
        self.last = None          # (when, events sent, Life OS's counts)
        self.last_error = None    # (when, message)
        self.reload()

    def reload(self):
        """Re-read [CalendarSync]; the background loop follows the new switch and interval."""
        config = self.app.config
        section = 'CalendarSync'
        has = config.has_section(section)
        self.enabled = has and config.getboolean(section, 'enabled', fallback=False)
        self.interval = max(5, config.getint(section, 'interval_minutes', fallback=15) if has else 15) * 60
        self.days_back = max(0, config.getint(section, 'days_back', fallback=1) if has else 1)
        self.days_ahead = max(1, min(60, config.getint(section, 'days_ahead', fallback=14) if has else 14))
        self._wake.set()

    def ready(self):
        notes = getattr(self.app, 'notes_sync', None)
        return bool(notes and notes.api_key and notes.encryption_key and notes.ingest_url)

    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name='outlook-calendar-sync', daemon=True)
            self._thread.start()
        print(f"[CalendarSync] auto={'on' if self.enabled else 'off'}, every {self.interval // 60} min, "
              f"{self.days_back} day(s) back, {self.days_ahead} ahead")

    def sync_once(self, progress=None):
        """Read Outlook and send; returns Life OS's answer. progress(stage, text) is called along the way."""
        say = progress or (lambda stage, text: None)
        if not self.ready():
            raise RuntimeError('Notes Sync 的 Ingest URL / API Key / XOR Key 还没填（设置 → Notes Sync）')
        if not self._lock.acquire(blocking=False):
            raise RuntimeError('上一次同步还没结束')
        try:
            say('reading', f'正在读取 Outlook 日历（前 {self.days_back} 天到后 {self.days_ahead} 天）…')
            window, events = read_outlook(self.days_back, self.days_ahead)
            say('sending', f'读到 {len(events)} 个日程，正在发送到 Life OS…')
            answer = send(self.app.notes_sync, window, events)
            counts = answer.get('calendar') or {}
            self.last, self.last_error = (dt.datetime.now(), len(events), counts), None
            say('done', f"已同步 {len(events)} 个日程：新增 {counts.get('added', 0)}、更新 {counts.get('updated', 0)}、"
                        f"取消 {counts.get('cancelled', 0)}（{window['from']} ~ {window['to']}）")
            print(f"[CalendarSync] sent {len(events)} events {window}: {counts}")
            return answer
        except Exception as error:
            self.last_error = (dt.datetime.now(), f'{type(error).__name__}: {str(error)[:160]}')
            say('error', f'同步失败：{self.last_error[1]}')
            raise
        finally:
            if self._lock.locked():
                self._lock.release()

    def sync_now(self, progress=None):
        """On demand, in the background (the UI stays responsive)."""
        def work():
            try:
                self.sync_once(progress)
            except Exception as error:
                print(f"[CalendarSync] manual sync failed: {error}")
        threading.Thread(target=work, name='outlook-calendar-sync-now', daemon=True).start()

    def status_text(self):
        parts = [f"自动同步：{'开，每 ' + str(self.interval // 60) + ' 分钟' if self.enabled else '关'}"]
        if self.last:
            when, n, counts = self.last
            parts.append(f"上次成功：{when:%m-%d %H:%M}，{n} 个日程")
        if self.last_error and (not self.last or self.last_error[0] > self.last[0]):
            parts.append(f"上次失败：{self.last_error[0]:%m-%d %H:%M} {self.last_error[1]}")
        return '；'.join(parts)

    def _run(self):
        self._wake.wait(20)  # let Outlook and the app settle after start-up
        while True:
            self._wake.clear()
            if self.enabled and self.ready():
                try:
                    self.sync_once()
                except Exception as error:  # Outlook closed, network down: try again next round
                    print(f"[CalendarSync] this round failed: {type(error).__name__}: {str(error)[:160]}")
            self._wake.wait(self.interval if self.enabled else 3600)


class SyncToast:
    """A small always-on-top note in the bottom-right corner that follows a manual sync and fades out when done."""

    def __init__(self, root):
        import tkinter as tk
        self.root, self.window = root, tk.Toplevel(root)
        self.window.overrideredirect(True)
        self.window.attributes('-topmost', True)
        self.label = tk.Label(self.window, text='', justify='left', bg='#1f2420', fg='#f5f3ee', padx=14, pady=10,
                              font=('Microsoft YaHei UI', 10), wraplength=360)
        self.label.pack()
        self.show('reading', 'Outlook 日历同步…')

    def show(self, stage, text):
        colors = {'done': '#1f5f4a', 'error': '#b4432f'}
        self.label.configure(text=f"📅 {text}", bg=colors.get(stage, '#1f2420'))
        self.window.update_idletasks()
        w, h = self.window.winfo_reqwidth(), self.window.winfo_reqheight()
        x, y = self.window.winfo_screenwidth() - w - 24, self.window.winfo_screenheight() - h - 64
        self.window.geometry(f'+{x}+{y}')
        if stage in ('done', 'error'):
            self.root.after(6000 if stage == 'done' else 10000, self.window.destroy)


def sync_with_toast(app):
    """The hotkey's action: a manual sync with the corner note. Call on the UI thread."""
    toast = SyncToast(app.root)
    sync = getattr(app, 'calendar_sync', None)
    if sync is None:
        toast.show('error', 'Outlook 日历同步没有启动')
        return
    sync.sync_now(progress=lambda stage, text: app.root.after(0, toast.show, stage, text))


def _config():
    config = configparser.ConfigParser()
    config.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini'), encoding='utf-8')
    return config


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m fastshot.outlook_calendar')
    parser.add_argument('--once', action='store_true', help='read Outlook and send once')
    parser.add_argument('--dry-run', action='store_true', help='read Outlook and print, do not send')
    parser.add_argument('--days-back', type=int, default=1)
    parser.add_argument('--days-ahead', type=int, default=14)
    args = parser.parse_args(argv)
    window, events = read_outlook(args.days_back, args.days_ahead)
    print(f"read {len(events)} events {window}")
    for event in events[:30]:
        print(f"  {event['date']} {event['start'] or '全天'}-{event['end'] or ''} {event['title'][:50]}"
              f"{' @' + event['location'][:30] if event['location'] else ''}{' [cancelled]' if event['status'] == 'cancelled' else ''}")
    if args.dry_run:
        return 0
    from types import SimpleNamespace
    from fastshot.notes_sync import NotesSyncManager
    manager = NotesSyncManager(SimpleNamespace(config=_config()))
    if not manager.api_key or not manager.encryption_key:
        print("config.ini [NotesSync] needs api_key and encryption_key")
        return 2
    print(json.dumps(send(manager, window, events), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
