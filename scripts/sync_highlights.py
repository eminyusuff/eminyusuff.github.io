#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'highlights.json'
APPLE_DATA = ROOT / 'data' / 'apple_inbox.json'
OUT = ROOT / 'data' / 'highlights.generated.json'


def load_items(path):
    if not path.exists():
        return []
    obj = json.loads(path.read_text(encoding='utf-8'))
    return obj.get('items', [])


def normalize(item):
    item = dict(item)
    item.setdefault('type', 'news')
    item.setdefault('date', '')
    item.setdefault('end_date', '')
    item.setdefault('title', '')
    item.setdefault('location', '')
    item.setdefault('description', '')
    item.setdefault('url', '')
    item.setdefault('image', '')
    item.setdefault('source', 'manual')
    item.setdefault('status', 'approved')
    return item


def eligible(item):
    source = item.get('source', 'manual')
    status = item.get('status', 'approved')

    # Manually curated highlights require explicit approval.
    if source == 'manual':
        return status == 'approved'

    # A dedicated Apple Calendar called "Academic Website" is an explicit
    # publishing source. Both past and upcoming events may appear on the site.
    if source == 'apple_calendar':
        return status in {'attended', 'upcoming', 'confirmed'}

    # Reminders act as a quick-capture inbox. Only completed reminders are
    # considered confirmed enough to publish.
    if source == 'apple_reminders':
        return status == 'confirmed'

    return status == 'approved'


def dedupe(items):
    out = []
    seen = set()
    for item in items:
        key = (
            item.get('type', '').lower(),
            item.get('title', '').strip().lower(),
            (item.get('date') or '')[:10],
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def main():
    raw = load_items(DATA) + load_items(APPLE_DATA)
    items = [normalize(x) for x in raw]
    items = [x for x in items if eligible(x)]
    items = dedupe(items)
    items.sort(key=lambda x: x.get('date', ''), reverse=True)
    payload = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'items': items,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
