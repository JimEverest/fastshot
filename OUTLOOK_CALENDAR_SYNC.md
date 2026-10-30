# Outlook calendar → Life OS (v2.3.0)

Fastshot can send your **classic desktop Outlook** calendar to Life OS, so the morning brief, meeting prep and
meeting recordings know your schedule. No ICS publishing, no Graph permission and no PowerShell are needed:
Fastshot reads Outlook through its own COM interface on this machine (`pywin32`).

## Set up

1. Settings → **Notes Sync**: Ingest URL, API Key and XOR Key must be filled in (the same /ingest, envelope and key).
2. Settings → **Outlook Calendar**:
   - *Enable automatic sync* — on: every *Interval* minutes; off: only when you ask.
   - *Days back / Days ahead* — the window sent each time (default: yesterday to 14 days ahead).
   - **立即同步 / Sync now** — sync at once; the tab shows each step (reading Outlook → sending N → result).
3. Any time: **Shift+F9** (`hotkey_calendar_sync`; macOS Ctrl+Shift+9) syncs now with a note in the bottom-right corner.

Saved settings apply immediately (no restart).

## What is sent

Time, subject, place, organizer and attendees of each meeting in the window — **never the meeting body**.
Private appointments are sent as "私人安排" with their time only. Each send is the whole calendar for that window:
a meeting you delete in Outlook is marked cancelled in Life OS.

## From CMD (for testing)

    python -m fastshot.outlook_calendar --dry-run    # read and print, send nothing
    python -m fastshot.outlook_calendar --once       # read and send once

Only classic Outlook is supported (the "new Outlook" has no COM interface).
