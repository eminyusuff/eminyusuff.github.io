#!/usr/bin/env python3
"""Sync a dedicated macOS Calendar and Reminders list into the website repo.

Privacy/safety design:
- Reads ONLY Calendar named "Academic Website".
- Reads ONLY Reminders list named "Academic Website".
- Writes candidate records to data/apple_inbox.json.
- Optionally matches a photo from ~/Pictures/AcademicSiteInbox by YYYY-MM-DD prefix.

This script is intended to run locally on the owner's Mac. GitHub Actions cannot
read local Apple Calendar/Reminders data directly.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

CALENDAR_NAME = "Academic Website"
REMINDERS_LIST = "Academic Website"
PHOTO_INBOX = Path.home() / "Pictures" / "AcademicSiteInbox"
REPO = Path(__file__).resolve().parents[1]
OUTFILE = REPO / "data" / "apple_inbox.json"
EVENT_ASSETS = REPO / "assets" / "events"


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, text=True, capture_output=True)


def run_jxa(source: str) -> list[dict]:
    proc = run(["osascript", "-l", "JavaScript", "-e", source])
    text = proc.stdout.strip()
    return json.loads(text) if text else []


def calendar_items() -> list[dict]:
    script = r'''
ObjC.import('Foundation');
const app = Application('Calendar');
app.includeStandardAdditions = true;
const matches = app.calendars.whose({name: 'Academic Website'})();
if (!matches.length) { JSON.stringify([]); }
else {
  const cal = matches[0];
  const now = new Date();
  const from = new Date(now.getTime() - 365 * 24 * 3600 * 1000);
  const to = new Date(now.getTime() + 365 * 24 * 3600 * 1000);
  const items = cal.events().map(e => {
    let sd = null, ed = null, loc = '', desc = '';
    try { sd = e.startDate(); } catch (_) {}
    try { ed = e.endDate(); } catch (_) {}
    try { loc = e.location() || ''; } catch (_) {}
    try { desc = e.description() || ''; } catch (_) {}
    if (!sd || sd < from || sd > to) return null;
    return {
      source: 'apple_calendar',
      type: 'conference',
      title: e.summary() || '',
      date: sd.toISOString(),
      end_date: ed ? ed.toISOString() : null,
      location: loc,
      description: desc,
      status: (ed && ed < now) ? 'attended' : 'upcoming'
    };
  }).filter(Boolean);
  JSON.stringify(items);
}
'''
    return run_jxa(script)


def reminder_items() -> list[dict]:
    script = r'''
const app = Application('Reminders');
const matches = app.lists.whose({name: 'Academic Website'})();
if (!matches.length) { JSON.stringify([]); }
else {
  const list = matches[0];
  const items = list.reminders().map(r => {
    let due = null, body = '', completed = false, completion = null;
    try { due = r.dueDate(); } catch (_) {}
    try { body = r.body() || ''; } catch (_) {}
    try { completed = !!r.completed(); } catch (_) {}
    try { completion = r.completionDate(); } catch (_) {}
    const name = r.name() || '';
    let type = 'award';
    if (/^(grant|fellowship|bursary)\s*:/i.test(name)) type = 'grant';
    else if (/^(conference|workshop|meeting)\s*:/i.test(name)) type = 'conference';
    else if (/^(award|prize)\s*:/i.test(name)) type = 'award';
    const title = name.replace(/^(grant|fellowship|bursary|conference|workshop|meeting|award|prize)\s*:\s*/i, '');
    return {
      source: 'apple_reminders',
      type,
      title,
      date: (due || completion) ? (due || completion).toISOString() : null,
      end_date: null,
      location: '',
      description: body,
      status: completed ? 'confirmed' : 'pending'
    };
  });
  JSON.stringify(items);
}
'''
    return run_jxa(script)


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:80] or "event"


def attach_matching_photo(item: dict) -> dict:
    iso = item.get("date")
    if not iso:
        return item
    try:
        date_prefix = datetime.fromisoformat(iso.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return item

    if not PHOTO_INBOX.exists():
        return item

    candidates = sorted(
        p for p in PHOTO_INBOX.iterdir()
        if p.is_file()
        and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        and p.name.startswith(date_prefix)
    )
    if not candidates:
        return item

    src = candidates[0]
    EVENT_ASSETS.mkdir(parents=True, exist_ok=True)
    dest_name = f"{date_prefix}-{slugify(item.get('title', 'event'))}{src.suffix.lower()}"
    dest = EVENT_ASSETS / dest_name
    if not dest.exists() or src.stat().st_mtime > dest.stat().st_mtime:
        shutil.copy2(src, dest)
    item["image"] = str(dest.relative_to(REPO)).replace(os.sep, "/")
    return item


def dedupe(items: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for item in items:
        key = (
            item.get("source"),
            item.get("type"),
            item.get("title", "").strip().lower(),
            (item.get("date") or "")[:10],
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def main() -> int:
    if sys.platform != "darwin":
        print("This script must run on macOS.", file=sys.stderr)
        return 2

    items = calendar_items() + reminder_items()
    items = [attach_matching_photo(x) for x in dedupe(items)]
    items.sort(key=lambda x: x.get("date") or "", reverse=True)

    payload = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "calendar": CALENDAR_NAME,
        "reminders_list": REMINDERS_LIST,
        "items": items,
    }
    OUTFILE.parent.mkdir(parents=True, exist_ok=True)
    OUTFILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(items)} item(s) to {OUTFILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
