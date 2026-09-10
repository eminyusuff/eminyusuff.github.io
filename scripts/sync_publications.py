#!/usr/bin/env python3
"""Verify newly discovered scholarly works and render published proceedings papers.

Policy:
- Google Scholar is discovery only.
- Crossref is used to verify that a work has a publisher/DOI record.
- Only journal-article and proceedings-article records are considered publications.
- Only proceedings-article records are auto-rendered in the Conference Papers section.
- Posters, abstracts, talks, registrations, and conference-program-only entries are excluded.
- Seeded records are manually verified and provide a reliable baseline if APIs are unavailable.
- Every publication card is linked to an official DOI, publisher, or journal record when available.
"""

from __future__ import annotations

import html
import json
import re
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SCHOLAR = ROOT / "data" / "scholar_publications.json"
SEED = ROOT / "data" / "publications_seed.json"
OUT = ROOT / "data" / "verified_publications.json"
INDEX = ROOT / "index.html"

ALLOWED_TYPES = {"journal-article", "proceedings-article"}
AUTO_START = "    <!-- AUTO VERIFIED CONFERENCE PAPERS START -->"
AUTO_END = "    <!-- AUTO VERIFIED CONFERENCE PAPERS END -->"
CONFERENCE_LABEL = (
    '    <div class="pub-block-label" style="margin-top:2rem">'
    "Conference Papers (Peer-Reviewed)</div>"
)
CARD_SCRIPT_START = "<!-- PUBLICATION CARD LINKS START -->"
CARD_SCRIPT_END = "<!-- PUBLICATION CARD LINKS END -->"

# Official landing pages for legacy/static publications that were originally
# rendered without links in index.html. DOI links are preferred when present.
STATIC_PUBLICATION_LINKS = {
    "bedensel engelli yuzuculerde cikis suresinin govde esnekligi aerobik endurans ve anaerobik guc ile iliskisi":
        "https://dergipark.org.tr/en/pub/jetr/issue/56637/512289",
    "a case study as a multisensory integration model weakly electric fish":
        "https://www.turkiyeklinikleri.com/article/en-coklu-duyusal-entegrasyon-modeli-olarak-ornek-bir-calisma-zayif-elektrik-baligi-104853.html",
    "reshaping active sensing via closing a feedback loop around free behavior":
        "https://doi.org/10.1109/SIU61531.2024.10601043",
    "tracking the nodal point of weakly electric fish using artificial neural networks":
        "https://doi.org/10.1109/SIU59756.2023.10223776",
    "system identification of the target tracking behavior of zebrafish during rheotaxis":
        "https://doi.org/10.1109/SIU55565.2022.9864905",
}


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower().replace("ı", "i")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def title_similarity(a: str, b: str) -> float:
    aa, bb = fold(a), fold(b)
    if not aa or not bb:
        return 0.0
    if aa == bb:
        return 1.0
    return SequenceMatcher(None, aa, bb).ratio()


def year_from_crossref(item: dict) -> str:
    for key in ("published-print", "published-online", "published", "issued"):
        parts = item.get(key, {}).get("date-parts", [])
        if parts and parts[0]:
            return str(parts[0][0])
    return ""


def author_list(item: dict) -> list[str]:
    out = []
    for author in item.get("author", []) or []:
        given = (author.get("given") or "").strip()
        family = (author.get("family") or "").strip()
        name = " ".join(x for x in [given, family] if x)
        if name:
            out.append(name)
    return out


def crossref_verify(work: dict) -> dict | None:
    title = (work.get("title") or "").strip()
    if not title:
        return None

    params = urlencode(
        {
            "query.title": title,
            "query.author": "Emin Yusuf Aydin",
            "rows": 5,
            "select": (
                "DOI,title,type,container-title,published-print,"
                "published-online,published,issued,author,publisher,URL"
            ),
        }
    )
    url = f"https://api.crossref.org/works?{params}"
    req = Request(
        url,
        headers={
            "User-Agent": (
                "eminyusuff.github.io academic-site-sync/1.0 "
                "(mailto:eminyusufaydin@gmail.com)"
            )
        },
    )
    try:
        with urlopen(req, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return None
    except Exception:
        return None

    candidates = payload.get("message", {}).get("items", [])
    best = None
    best_score = 0.0
    for item in candidates:
        if item.get("type") not in ALLOWED_TYPES:
            continue
        candidate_title = ((item.get("title") or [""])[0] or "").strip()
        score = title_similarity(title, candidate_title)
        if score > best_score:
            best_score = score
            best = item

    if not best or best_score < 0.88:
        return None

    doi = (best.get("DOI") or "").strip()
    if not doi:
        return None

    container = ((best.get("container-title") or [""])[0] or "").strip()
    return {
        "type": best.get("type", ""),
        "title": ((best.get("title") or [title])[0] or title).strip(),
        "authors": author_list(best),
        "venue": container or (work.get("venue") or ""),
        "publisher": (best.get("publisher") or "").strip(),
        "year": year_from_crossref(best) or str(work.get("year") or ""),
        "doi": doi,
        "url": f"https://doi.org/{doi}",
        "source": "crossref_verified_from_google_scholar",
        "status": "published",
    }


def dedupe(items: list[dict]) -> list[dict]:
    out = []
    seen = set()
    for item in items:
        doi = fold(item.get("doi", ""))
        key = ("doi", doi) if doi else ("title", fold(item.get("title", "")))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def discover_verified() -> list[dict]:
    scholar_items = load_json(SCHOLAR).get("items", [])
    existing = load_json(OUT).get("items", [])
    seed_items = load_json(SEED).get("items", [])

    known_titles = {fold(x.get("title", "")) for x in existing + seed_items}
    current_year = datetime.now(timezone.utc).year
    discovered = []

    for work in scholar_items:
        try:
            year = int(str(work.get("year") or "0"))
        except ValueError:
            year = 0
        if year and year < current_year - 1:
            continue
        if fold(work.get("title", "")) in known_titles:
            continue
        verified = crossref_verify(work)
        if verified:
            discovered.append(verified)
            known_titles.add(fold(verified.get("title", "")))

    combined = dedupe(seed_items + existing + discovered)
    combined.sort(
        key=lambda x: (str(x.get("year") or ""), x.get("title") or ""),
        reverse=True,
    )
    return combined


def initials(name: str) -> str:
    parts = name.split()
    if not parts:
        return ""
    family = parts[-1]
    given = parts[:-1]
    ini = " ".join(f"{p[0]}." for p in given if p)
    return f"{family}, {ini}".strip()


def render_authors(item: dict) -> str:
    if item.get("authors_html"):
        return item["authors_html"]
    authors = item.get("authors", []) or []
    rendered = []
    for name in authors:
        value = html.escape(initials(name))
        if "aydin" in fold(name):
            value = f"<strong>{value}</strong>"
        rendered.append(value)
    if not rendered:
        return ""
    if len(rendered) == 1:
        return rendered[0]
    return ", ".join(rendered[:-1]) + " &amp; " + rendered[-1]


def render_card(item: dict) -> str:
    title = html.escape(item.get("display_title") or item.get("title") or "")
    url = html.escape(item.get("url") or "", quote=True)
    venue = html.escape(item.get("venue") or "")
    publisher = html.escape(item.get("publisher") or "")
    year = html.escape(str(item.get("year") or ""))
    doi = html.escape(item.get("doi") or "")
    authors = render_authors(item)

    venue_parts = [x for x in [venue, publisher, year] if x]
    venue_line = " · ".join(venue_parts)

    title_html = f'<a href="{url}" target="_blank">{title}</a>' if url else title
    doi_html = ""
    if doi and url:
        doi_html = (
            '        <div class="pub-links">\n'
            f'          <a href="{url}" class="pub-link-btn" target="_blank">DOI</a>\n'
            "        </div>\n"
        )

    return (
        '    <div class="pub-card auto-pub-card">\n'
        '      <div class="pub-thumb">\n'
        '        <svg viewBox="0 0 130 100" xmlns="http://www.w3.org/2000/svg">\n'
        '          <rect width="130" height="100" fill="#eef3f8"/>\n'
        '          <rect x="18" y="20" width="94" height="60" rx="7" fill="#ffffff" stroke="#8aa4bf"/>\n'
        '          <text x="65" y="44" text-anchor="middle" font-size="14" fill="#315b7d" font-family="sans-serif" font-weight="bold">IEEE</text>\n'
        '          <text x="65" y="60" text-anchor="middle" font-size="8" fill="#667788" font-family="sans-serif">Conference Proceedings</text>\n'
        '          <path d="M35 70 L95 70" stroke="#315b7d" stroke-width="1.4"/>\n'
        '        </svg>\n'
        '      </div>\n'
        '      <div class="pub-body">\n'
        f'        <p class="pub-ptitle">{title_html}</p>\n'
        f'        <p class="pub-authors">{authors}</p>\n'
        f'        <p class="pub-venue">{venue_line}</p>\n'
        f"{doi_html}"
        "      </div>\n"
        "    </div>"
    )


def add_missing_static_links(text: str) -> str:
    """Link legacy publication titles that predate the automated renderer."""
    pattern = re.compile(r'<p class="pub-ptitle">(?!\s*<a\b)(.*?)</p>', re.DOTALL)

    def repl(match: re.Match) -> str:
        raw_title = match.group(1)
        plain_title = html.unescape(re.sub(r"<[^>]+>", "", raw_title)).strip()
        url = STATIC_PUBLICATION_LINKS.get(fold(plain_title))
        if not url:
            return match.group(0)
        return (
            '<p class="pub-ptitle">'
            f'<a href="{html.escape(url, quote=True)}" target="_blank">{raw_title}</a>'
            "</p>"
        )

    return pattern.sub(repl, text)


def add_publication_card_click_behavior(text: str) -> str:
    """Make the complete publication card open its title/DOI link."""
    block = """<!-- PUBLICATION CARD LINKS START -->
<script>
document.querySelectorAll('#publications .pub-card').forEach((card) => {
  const target = card.querySelector('.pub-ptitle a[href], .pub-links a[href]');
  if (!target) return;

  card.style.cursor = 'pointer';
  card.setAttribute('tabindex', '0');
  card.setAttribute('role', 'link');
  card.setAttribute('aria-label', `Open publication: ${card.querySelector('.pub-ptitle')?.innerText || 'publication'}`);

  const openPublication = () => window.open(target.href, '_blank', 'noopener,noreferrer');

  card.addEventListener('click', (event) => {
    if (event.target.closest('a')) return;
    openPublication();
  });

  card.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      openPublication();
    }
  });
});
</script>
<!-- PUBLICATION CARD LINKS END -->"""

    if CARD_SCRIPT_START in text and CARD_SCRIPT_END in text:
        start = text.index(CARD_SCRIPT_START)
        end = text.index(CARD_SCRIPT_END) + len(CARD_SCRIPT_END)
        return text[:start] + block + text[end:]

    if "</body>" not in text:
        raise RuntimeError("Closing body tag not found in index.html")
    return text.replace("</body>", block + "\n</body>", 1)


def render_publications(items: list[dict]) -> None:
    proceedings = [
        x
        for x in items
        if x.get("type") == "proceedings-article"
        and x.get("status") == "published"
        and x.get("doi")
    ]

    text = INDEX.read_text(encoding="utf-8")
    if AUTO_START in text and AUTO_END in text:
        start = text.index(AUTO_START)
        end = text.index(AUTO_END) + len(AUTO_END)
        base_text = text[:start] + text[end:]
    else:
        base_text = text

    cards = []
    for item in proceedings:
        doi = item.get("doi") or ""
        title = item.get("display_title") or item.get("title") or ""
        if doi and doi in base_text:
            continue
        if title and title in base_text:
            continue
        cards.append(render_card(item))

    block = AUTO_START
    if cards:
        block += "\n" + "\n\n".join(cards) + "\n"
    block += AUTO_END

    if AUTO_START in text and AUTO_END in text:
        start = text.index(AUTO_START)
        end = text.index(AUTO_END) + len(AUTO_END)
        new_text = text[:start] + block + text[end:]
    else:
        if CONFERENCE_LABEL not in text:
            raise RuntimeError("Conference Papers label not found in index.html")
        new_text = text.replace(
            CONFERENCE_LABEL,
            CONFERENCE_LABEL + "\n\n" + block,
            1,
        )

    new_text = add_missing_static_links(new_text)
    new_text = add_publication_card_click_behavior(new_text)
    INDEX.write_text(new_text, encoding="utf-8")


def main() -> int:
    items = discover_verified()
    payload = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": (
            "Scholar discovers candidates; Crossref/publisher DOI records verify publication. "
            "Posters and conference-program-only items are excluded."
        ),
        "items": items,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render_publications(items)
    print(f"Verified {len(items)} publication record(s); rendered published proceedings papers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
