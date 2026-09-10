#!/usr/bin/env python3
import html
import json
import re
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'highlights.json'
APPLE_DATA = ROOT / 'data' / 'apple_inbox.json'
PROFILE_DATA = ROOT / 'data' / 'profile.json'
OUT = ROOT / 'data' / 'highlights.generated.json'
INDEX = ROOT / 'index.html'

BADGE_CLASS = {
    'publication': 'badge-green',
    'conference': 'badge-orange',
    'workshop': 'badge-teal',
    'training': 'badge-blue',
    'award': 'badge-purple',
    'grant': 'badge-purple',
    'degree': 'badge-purple',
}


def load_items(path):
    if not path.exists():
        return []
    obj = json.loads(path.read_text(encoding='utf-8'))
    return obj.get('items', [])


def load_profile():
    if not PROFILE_DATA.exists():
        return {}
    return json.loads(PROFILE_DATA.read_text(encoding='utf-8'))


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
    if source == 'manual':
        return status == 'approved'
    if source == 'apple_calendar':
        return status in {'attended', 'upcoming', 'confirmed'}
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


def display_date(value):
    if not value:
        return ''
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    try:
        if len(value) >= 7 and value[4] == '-':
            year = value[:4]
            month = int(value[5:7])
            if 1 <= month <= 12:
                return f'{months[month - 1]} {year}'
        return value[:4] if len(value) >= 4 else value
    except Exception:
        return value


def render_news(items):
    rows = []
    for item in items:
        badge = BADGE_CLASS.get(item.get('type'), 'badge-gray')
        date_label = html.escape(display_date(item.get('date', '')))
        title = html.escape(item.get('title', ''))
        description = html.escape(item.get('description', ''))
        location = html.escape(item.get('location', ''))
        url = item.get('url', '')
        image = item.get('image', '')
        status = item.get('status', '')

        if url:
            title_html = f'<a href="{html.escape(url, quote=True)}" target="_blank"><strong>{title}</strong></a>'
        else:
            title_html = f'<strong>{title}</strong>'

        detail_parts = []
        if description:
            detail_parts.append(description)
        if location:
            detail_parts.append(location)
        details = ' — '.join(detail_parts)

        status_prefix = ''
        if item.get('source') == 'apple_calendar' and status == 'upcoming':
            status_prefix = '<em>Upcoming:</em> '

        image_html = ''
        if image:
            safe_image = html.escape(image, quote=True)
            image_html = (
                f'<br><a href="{safe_image}" target="_blank">'
                f'<img src="{safe_image}" alt="{title}" '
                'style="margin-top:.65rem;max-width:260px;width:100%;height:auto;border-radius:8px;border:1px solid var(--border);">'
                '</a>'
            )

        text = f'{status_prefix}{title_html}'
        if details:
            text += f' — {details}'
        text += image_html

        rows.append(
            '      <div class="news-row">\n'
            f'        <span class="badge {badge}">{date_label}</span>\n'
            f'        <p class="news-text">{text}</p>\n'
            '      </div>'
        )

    return (
        '  <!-- NEWS -->\n'
        '  <section id="news">\n'
        '    <h2 class="sec-title">News</h2>\n'
        '    <div class="news-list">\n'
        + '\n'.join(rows)
        + '\n    </div>\n'
        '  </section>\n\n'
    )


def update_profile(text, profile):
    if not profile:
        return text

    role = html.escape(profile.get('role', ''))
    institution = html.escape(profile.get('institution', ''))
    location = html.escape(profile.get('location', ''))
    about = profile.get('about', [])

    if role:
        text = re.sub(
            r'<p class="hero-pos">.*?</p>',
            f'<p class="hero-pos">{role}</p>',
            text,
            count=1,
            flags=re.DOTALL,
        )

    if institution or location:
        institution_line = ' · '.join(x for x in [institution, location] if x)
        text = re.sub(
            r'(<i class="fas fa-university"></i>\s*<span>).*?(</span>)',
            rf'\1{institution_line}\2',
            text,
            count=1,
            flags=re.DOTALL,
        )

    if about:
        about_html = '\n'.join(
            f'      <p>{html.escape(paragraph)}</p>'
            for paragraph in about
            if str(paragraph).strip()
        )
        text = re.sub(
            r'(<section id="about">.*?<div class="about">)\s*.*?\s*(</div>\s*</section>)',
            rf'\1\n{about_html}\n    \2',
            text,
            count=1,
            flags=re.DOTALL,
        )

    return text


def update_index(items, profile):
    if not INDEX.exists():
        return
    text = INDEX.read_text(encoding='utf-8')
    text = update_profile(text, profile)

    start_marker = '  <!-- NEWS -->'
    end_marker = '  <!-- PUBLICATIONS -->'
    start = text.find(start_marker)
    end = text.find(end_marker)
    if start == -1 or end == -1 or end <= start:
        raise RuntimeError('Could not locate NEWS/PUBLICATIONS markers in index.html')
    new_text = text[:start] + render_news(items) + text[end:]
    INDEX.write_text(new_text, encoding='utf-8')


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
    update_index(items, load_profile())


if __name__ == '__main__':
    main()
