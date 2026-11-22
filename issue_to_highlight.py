#!/usr/bin/env python3
"""Turn an "Academic Highlight" GitHub issue form into an entry in data/highlights.json.

Called by .github/workflows/issue-to-highlight.yml. Inputs come from environment
variables (never from the command line, so issue text cannot inject shell code):

  ISSUE_BODY    the issue body written by the issue form
  ISSUE_NUMBER  issue number (stored for traceability)
  GITHUB_TOKEN  optional, used only as a fallback to download an attached photo

Exit code 0 = item added/updated. Exit code 1 = validation error; the message is
written to issue_result.md so the workflow can post it as a comment.
"""

from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "highlights.json"
EVENTS = ROOT / "assets" / "events"
RESULT = ROOT / "issue_result.md"

ALLOWED_TYPES = {
    "conference", "workshop", "talk", "award", "grant", "travel_grant",
    "fellowship", "publication", "training", "degree", "news",
}
DATE_RE = re.compile(r"^\d{4}-\d{2}(-\d{2})?$")
IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}

# Issue-form label -> highlights.json field
FIELDS = {
    "type": "type",
    "start date": "date",
    "date": "date",
    "end date": "end_date",
    "title": "title",
    "location": "location",
    "description": "description",
    "presentation type": "presentation_type",
    "presented work title": "work_title",
    "public url": "url",
    "photo": "photo",
    "publication approval": "approval",
}


def parse_issue_form(body: str) -> dict:
    """Issue forms render as '### Label\\n\\nvalue' blocks."""
    out: dict[str, str] = {}
    for block in re.split(r"^###\s+", body or "", flags=re.MULTILINE)[1:]:
        label, _, value = block.partition("\n")
        key = FIELDS.get(label.strip().lower())
        if not key:
            continue
        value = value.strip()
        if value == "_No response_":
            value = ""
        out[key] = value
    return out


def slugify(text: str, limit: int = 40) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:limit].rstrip("-") or "event"


def first_image_url(photo_field: str) -> str:
    match = re.search(r"\((https://[^)\s]+)\)", photo_field) or re.search(r'src="(https://[^"]+)"', photo_field)
    if not match:
        match = re.search(r"(https://\S+)", photo_field)
    return match.group(1) if match else ""


def download_image(url: str, stem: str) -> str:
    """Save the attachment under assets/events/. Returns the relative path or ''."""
    attempts = [{}]
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        attempts.append({"Authorization": f"Bearer {token}"})
    for headers in attempts:
        try:
            req = Request(url, headers={"User-Agent": "academic-site-bot", **headers})
            with urlopen(req, timeout=30) as resp:
                ctype = resp.headers.get_content_type()
                data = resp.read(15 * 1024 * 1024)
            ext = IMAGE_TYPES.get(ctype)
            if not ext:
                continue
            EVENTS.mkdir(parents=True, exist_ok=True)
            path = EVENTS / f"{stem}{ext}"
            path.write_bytes(data)
            return path.relative_to(ROOT).as_posix()
        except Exception as exc:  # network / auth problems: try next option
            print(f"Photo download attempt failed: {exc}")
    return ""


def fail(message: str) -> int:
    RESULT.write_text(f"⚠️ This highlight was **not** published:\n\n{message}\n\n"
                      "Edit the issue (or open a new one) and try again.\n", encoding="utf-8")
    print(message)
    return 1


def main() -> int:
    form = parse_issue_form(os.environ.get("ISSUE_BODY", ""))

    if "[x]" not in form.get("approval", "").lower():
        return fail("The publication approval box is not ticked.")

    item_type = form.get("type", "").strip().lower()
    if item_type not in ALLOWED_TYPES:
        return fail(f"Unknown type `{item_type}`.")
    title = form.get("title", "").strip()
    if not title:
        return fail("Title is empty.")
    start = form.get("date", "").strip()
    if not DATE_RE.match(start):
        return fail(f"Start date `{start}` is not in YYYY-MM-DD (or YYYY-MM) format.")
    end = form.get("end_date", "").strip()
    if end and not DATE_RE.match(end):
        return fail(f"End date `{end}` is not in YYYY-MM-DD format.")
    url = form.get("url", "").strip()
    if url and not url.startswith(("http://", "https://")):
        return fail(f"Public URL `{url}` must start with http:// or https://.")

    item = {
        "type": item_type,
        "date": start,
        "title": title,
        "location": form.get("location", "").strip(),
        "description": " ".join(form.get("description", "").split()),
        "url": url,
        "image": "",
        "source": "manual",
        "status": "approved",
        "issue": int(os.environ.get("ISSUE_NUMBER") or 0) or None,
    }
    if end:
        item["end_date"] = end
    for key in ("presentation_type", "work_title"):
        if form.get(key, "").strip():
            item[key] = form[key].strip()

    photo_note = ""
    image_url = first_image_url(form.get("photo", ""))
    if image_url:
        item["image"] = download_image(image_url, f"{start[:10]}-{slugify(title)}")
        photo_note = (f"\n- Photo saved as `{item['image']}`" if item["image"]
                      else "\n- ⚠️ The photo could not be downloaded; add it manually to `assets/events/`.")

    data = json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else {"version": 2, "items": []}
    items = data.setdefault("items", [])

    # Same issue or same (type, title, date) -> update instead of duplicating.
    def same(existing: dict) -> bool:
        if item["issue"] and existing.get("issue") == item["issue"]:
            return True
        return (existing.get("type") == item["type"]
                and existing.get("title", "").strip().lower() == title.lower()
                and (existing.get("date") or "")[:10] == start[:10])

    replaced = False
    for i, existing in enumerate(items):
        if same(existing):
            items[i] = item
            replaced = True
            break
    if not replaced:
        items.append(item)
    items.sort(key=lambda x: x.get("date", ""), reverse=True)

    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    verb = "Updated" if replaced else "Added"
    RESULT.write_text(
        f"✅ {verb} on the website: **{title}** ({item_type}, {start})"
        f"{photo_note}\n\nThe page refreshes within a few minutes on https://eminyusuff.github.io/#news\n",
        encoding="utf-8",
    )
    print(f"{verb}: {title}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
