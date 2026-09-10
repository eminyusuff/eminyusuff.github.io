#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'highlights.json'
OUT = ROOT / 'data' / 'highlights.generated.json'


def load_items():
    if not DATA.exists():
        return []
    obj = json.loads(DATA.read_text(encoding='utf-8'))
    return obj.get('items', [])


def normalize(item):
    item = dict(item)
    item.setdefault('type', 'news')
    item.setdefault('date', '')
    item.setdefault('title', '')
    item.setdefault('location', '')
    item.setdefault('description', '')
    item.setdefault('url', '')
    item.setdefault('image', '')
    item.setdefault('source', 'manual')
    item.setdefault('status', 'approved')
    return item


def main():
    items = [normalize(x) for x in load_items() if x.get('status', 'approved') == 'approved']
    items.sort(key=lambda x: x.get('date', ''), reverse=True)
    payload = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'items': items,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
