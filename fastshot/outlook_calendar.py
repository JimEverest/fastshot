# fastshot/outlook_calendar.py
"""Send the desktop Outlook calendar to Life OS, so its morning brief, meeting prep and recordings know the schedule.

Works with classic desktop Outlook on Windows (not the "new Outlook"): it reads the calendar through Outlook's own
COM interface on this machine — no ICS publishing, no Graph permission, no PowerShell. Every `interval_minutes`
it sends the meetings from `days_back` days ago to `days_ahead` days ahead (time, subject, place, organizer,
attendees — never the meeting body) through the same encrypted /ingest envelope NotesSync uses. Life OS treats
each send as the whole calendar for that window: a meeting removed in Outlook is marked cancelled there.

Private appointments (Sensitivity = private) go as "私人安排" with only their time.

config.ini:
    [CalendarSync]
    enabled = True
    interval_minutes = 15
    days_back = 1
    days_ahead = 14
The /ingest address and the two keys come from [NotesSync] (ingest_url, api_key, encryption_key).

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
    """The background sender, started by Fastshot when [CalendarSync] enabled = True."""

    def __init__(self, app):
        self.app = app
        config = app.config
        section = 'CalendarSync'
        self.enabled = config.has_section(section) and config.getboolean(section, 'enabled', fallback=False)
        self.interval = max(5, config.getint(section, 'interval_minutes', fallback=15)) * 60 if self.enabled else 0
        self.days_back = config.getint(section, 'days_back', fallback=1) if self.enabled else 1
        self.days_ahead = config.getint(section, 'days_ahead', fallback=14) if self.enabled else 14
        self._stop = threading.Event()
        self.last = None

    def start(self):
        if not self.enabled:
            print("[CalendarSync] disabled")
            return
        if not getattr(self.app, 'notes_sync', None) or not self.app.notes_sync.api_key:
            print("[CalendarSync] needs [NotesSync] ingest_url / api_key / encryption_key; not started")
            return
        threading.Thread(target=self._run, name='outlook-calendar-sync', daemon=True).start()
        print(f"[CalendarSync] every {self.interval // 60} min, {self.days_back} day(s) back, {self.days_ahead} ahead")

    def stop(self):
        self._stop.set()

    def sync_once(self):
        window, events = read_outlook(self.days_back, self.days_ahead)
        answer = send(self.app.notes_sync, window, events)
        self.last = (dt.datetime.now(), len(events), answer.get('calendar'))
        print(f"[CalendarSync] sent {len(events)} events {window}: {answer.get('calendar')}")
        return answer

    def _run(self):
        time.sleep(20)  # let Outlook and the app settle after start-up
        while not self._stop.is_set():
            try:
                self.sync_once()
            except Exception as error:  # Outlook closed, network down: try again next round
                print(f"[CalendarSync] this round failed: {type(error).__name__}: {str(error)[:160]}")
            self._stop.wait(self.interval)


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
