#!/usr/bin/env python3
"""Best-effort Google Scholar profile sync.

Google Scholar does not expose an official public API. This script therefore makes
one lightweight request to the owner's public profile and caches the visible works.
If Scholar rate-limits or changes markup, the existing cache is preserved and the
site build continues successfully.
"""

from __future__ import annotations

import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "scholar_publications.json"
PROFILE_ID = "3kCPuu8AAAAJ"
PROFILE_URL = (
    "https://scholar.google.com/citations"
    f"?user={PROFILE_ID}&hl=en&pagesize=100&cstart=0"
)


def clean_fragment(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value or "")
    return html.unescape(value).strip()


def fetch_html() -> str:
    req = Request(
        PROFILE_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urlopen(req, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_works(page: str) -> list[dict]:
    rows = re.findall(
        r'<tr[^>]*class="[^"]*gsc_a_tr[^"]*"[^>]*>(.*?)</tr>',
        page,
        flags=re.DOTALL | re.IGNORECASE,
    )
    works: list[dict] = []

    for row in rows:
        title_match = re.search(
            r'<a[^>]*class="[^"]*gsc_a_at[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            row,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if not title_match:
            continue

        rel_url, title_html = title_match.groups()
        title = clean_fragment(title_html)
        if not title:
            continue

        gray = re.findall(
            r'<div[^>]*class="[^"]*gs_gray[^"]*"[^>]*>(.*?)</div>',
            row,
            flags=re.DOTALL | re.IGNORECASE,
        )
        authors = clean_fragment(gray[0]) if len(gray) > 0 else ""
        venue = clean_fragment(gray[1]) if len(gray) > 1 else ""

        year_match = re.search(r'class="[^"]*gsc_a_y[^"]*"[^>]*>.*?(\d{4})', row, re.DOTALL)
        if not year_match:
            year_match = re.search(r'>(\d{4})</(?:a|span)>', row)
        year = year_match.group(1) if year_match else ""

        cited_match = re.search(
            r'class="[^"]*gsc_a_ac[^"]*"[^>]*>(?:<a[^>]*>)?\s*(\d+)?',
            row,
            flags=re.DOTALL | re.IGNORECASE,
        )
        citations = int(cited_match.group(1)) if cited_match and cited_match.group(1) else 0

        works.append(
            {
                "title": title,
                "authors": authors,
                "venue": venue,
                "year": year,
                "url": urljoin("https://scholar.google.com", html.unescape(rel_url)),
                "citations": citations,
                "source": "google_scholar",
            }
        )

    return works


def main() -> int:
    try:
        page = fetch_html()
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"Scholar unavailable; preserving existing cache: {exc}")
        return 0
    except Exception as exc:
        print(f"Scholar sync skipped; preserving existing cache: {exc}")
        return 0

    lower = page.lower()
    if "unusual traffic" in lower or "captcha" in lower:
        print("Scholar rate-limited the request; preserving existing cache.")
        return 0

    works = parse_works(page)
    if not works:
        print("No Scholar works parsed; preserving existing cache.")
        return 0

    payload = {
        "version": 1,
        "profile_id": PROFILE_ID,
        "profile_url": f"https://scholar.google.com/citations?user={PROFILE_ID}&hl=en",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": works,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Cached {len(works)} Google Scholar work(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
