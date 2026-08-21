#!/usr/bin/env python3
"""Enrich discovered domains with current public identity and editorial signals."""

from __future__ import annotations

import argparse
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from common import ROOT, load_yaml, source_files


BUILD = ROOT / "build" / "discovery"
USER_AGENT = "Gatilab-Blog-Rankings-Research/0.2 (+https://github.com/wpgaurav/blog-rankings)"
GENERIC_HOSTS = {
    "medium.com", "github.com", "news.ycombinator.com", "dev.to", "bit.ai", "substack.com",
    "open.substack.com", "feedly.com", "bsky.app", "wordpress.com", "tag", "goodreads.com",
    "teacherspayteachers.com", "email.chartmogul.com", "people.inc", "linktr.ee", "t.co",
    "tinyurl.com", "lnkd.in", "mailchi.mp", "convertkit.com", "kit.com", "beehiiv.com",
    "flipboard.com", "tumblr.com", "podcasts.apple.com", "spotify.com", "soundcloud.com",
}
PARKED_WORDS = re.compile(r"(?i)(domain is for sale|buy this domain|parked domain|coming soon|account suspended)")
TITLE_SPLIT = re.compile(r"\s(?:\||–|—|:|-{1,2})\s")
PERSON_SCHEMA = re.compile(r'(?i)"@type"\s*:\s*(?:"Person"|\[[^\]]*"Person")')
ORG_SCHEMA = re.compile(r'(?i)"@type"\s*:\s*(?:"Organization"|"NewsMediaOrganization"|"EducationalOrganization"|\[[^\]]*"Organization")')
ARTICLE_SCHEMA = re.compile(r'(?i)"@type"\s*:\s*(?:"Article"|"BlogPosting"|"NewsArticle")')
COMPANY_TLDS = (".edu", ".gov", ".ac.uk", ".org.uk")

CATEGORY_WORDS = {
    "technology": {"technology", "tech", "software", "developer", "engineering", "cybersecurity", "security", "ai", "wordpress", "gadgets", "computing"},
    "business": {"business", "entrepreneur", "startup", "saas", "leadership", "management", "founder", "company", "operations", "commerce"},
    "marketing-seo": {"marketing", "seo", "search", "content", "copywriting", "social media", "analytics", "growth", "advertising", "conversion"},
    "personal-finance": {"personal finance", "money", "investing", "saving", "debt", "tax", "financial", "budget", "retirement", "wealth"},
    "science": {"science", "scientific", "research", "physics", "biology", "climate", "space", "chemistry", "astronomy", "laboratory"},
    "education": {"education", "teaching", "teacher", "learning", "school", "student", "higher education", "edtech", "classroom", "university"},
    "health": {"health", "wellness", "fitness", "nutrition", "mental health", "medical", "medicine", "doctor", "healthy", "public health"},
    "travel": {"travel", "traveler", "traveller", "destination", "trip", "tourism", "adventure", "vacation", "backpacking", "journey"},
    "food": {"food", "recipe", "cooking", "baking", "kitchen", "culinary", "restaurant", "chef", "nutrition", "dining"},
    "culture-entertainment": {"culture", "entertainment", "books", "film", "movies", "music", "gaming", "television", "criticism", "arts"},
}


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.in_title = False
        self.meta: dict[str, str] = {}
        self.canonical: str | None = None
        self.feed_url: str | None = None
        self.links: list[tuple[str, str]] = []
        self.viewport = False
        self.article_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): value or "" for key, value in attrs}
        lower_tag = tag.lower()
        if lower_tag == "title":
            self.in_title = True
        elif lower_tag == "article":
            self.article_count += 1
        elif lower_tag == "meta":
            key = (attributes.get("property") or attributes.get("name") or "").lower()
            content = attributes.get("content", "").strip()
            if key and content:
                self.meta.setdefault(key, content)
            if key == "viewport":
                self.viewport = True
        elif lower_tag == "link":
            rel = set(attributes.get("rel", "").lower().split())
            href = attributes.get("href", "")
            if "canonical" in rel and href:
                self.canonical = href
            link_type = attributes.get("type", "").lower()
            if "alternate" in rel and href and link_type in {"application/rss+xml", "application/atom+xml"}:
                self.feed_url = href
        elif lower_tag == "a" and attributes.get("href"):
            self.links.append((attributes["href"], attributes.get("title", "")))

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data.strip())


def root_url(host: str) -> str:
    return f"https://{host}/"


def clean_text(value: str, limit: int = 500) -> str:
    return re.sub(r"\s+", " ", value).strip()[:limit]


def classify_track(record: dict[str, Any], schema: dict[str, Any]) -> tuple[str, str]:
    existing_track = record.get("existing_track")
    if existing_track in {"independent", "publisher_company"}:
        return existing_track, "high"
    track_hints = record.get("track_hints", {})
    independent = int(track_hints.get("independent", 0))
    publisher = int(track_hints.get("publisher_company", 0))
    if record["host"].endswith(COMPANY_TLDS):
        return "publisher_company", "high"
    if record["host"].endswith(".substack.com"):
        return "independent", "standard"
    if independent >= 2 and independent >= publisher * 1.5:
        return "independent", "standard"
    if publisher >= 2 and publisher >= independent * 1.5:
        return "publisher_company", "standard"
    if schema.get("person") and not schema.get("organization"):
        return "independent", "high"
    if schema.get("organization") and not schema.get("person"):
        return "publisher_company", "standard"
    return ("independent", "provisional") if independent >= publisher else ("publisher_company", "provisional")


def fetch(record: dict[str, Any]) -> dict[str, Any]:
    url = root_url(record["host"])
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
    )
    try:
        with urllib.request.urlopen(request, timeout=12, context=ssl.create_default_context()) as response:
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                return {**record, "site_status": response.status, "accepted": False, "reject_reason": "not-html"}
            raw = response.read(1_500_000)
            html = raw.decode(response.headers.get_content_charset() or "utf-8", errors="replace")
            parser = SiteParser()
            parser.feed(html)
            title = clean_text(" ".join(parser.title_parts), 180)
            description = clean_text(
                parser.meta.get("description")
                or parser.meta.get("og:description")
                or parser.meta.get("twitter:description")
                or "",
                400,
            )
            site_name = clean_text(parser.meta.get("og:site_name", ""), 120)
            final_url = response.geturl()
            canonical = urllib.parse.urljoin(final_url, parser.canonical) if parser.canonical else final_url
            feed = urllib.parse.urljoin(final_url, parser.feed_url) if parser.feed_url else None
            lower_html = html[:800_000].lower()
            link_tokens = " ".join(href.lower() for href, _ in parser.links[:500])
            trust_signals = {
                "about": "about" in link_tokens,
                "contact": "contact" in link_tokens,
                "authors": any(token in link_tokens for token in ("author", "team", "contributors", "masthead")),
                "privacy": "privacy" in link_tokens,
                "disclosure": any(token in link_tokens for token in ("disclosure", "editorial-policy", "ethics", "corrections")),
            }
            schema = {
                "person": bool(PERSON_SCHEMA.search(html)),
                "organization": bool(ORG_SCHEMA.search(html)),
                "article": bool(ARTICLE_SCHEMA.search(html)),
            }
            text = " ".join(
                [
                    title,
                    description,
                    site_name,
                    " ".join(record.get("titles", [])),
                    " ".join(record.get("snippets", [])),
                    " ".join(record.get("direct_queries", [])),
                ]
            ).lower()
            relevance = sum(1 for word in CATEGORY_WORDS[record["category"]] if word in text)
            editorial_signal = bool(feed or parser.article_count or schema["article"] or any(token in lower_html for token in ("latest posts", "latest articles", "recent posts", "newsletter")))
            accepted = (
                response.status < 400
                and bool(title or site_name)
                and not PARKED_WORDS.search(f"{title} {description}")
                and relevance > 0
                and editorial_signal
            )
            track, track_confidence = classify_track(record, schema)
            name = site_name or TITLE_SPLIT.split(title, maxsplit=1)[0] or record["host"]
            return {
                **record,
                "site_status": response.status,
                "accepted": accepted,
                "reject_reason": None if accepted else "insufficient-editorial-or-category-signal",
                "final_url": final_url,
                "canonical_url": canonical,
                "name": clean_text(name, 120),
                "title": title,
                "description": description,
                "feed_url": feed,
                "html_bytes": len(raw),
                "viewport": parser.viewport,
                "article_count": parser.article_count,
                "trust_signals": trust_signals,
                "schema": schema,
                "category_relevance": relevance,
                "track": track,
                "track_confidence": track_confidence,
            }
    except urllib.error.HTTPError as error:
        return {**record, "site_status": error.code, "accepted": False, "reject_reason": f"http-{error.code}"}
    except Exception as error:
        return {**record, "site_status": None, "accepted": False, "reject_reason": str(error)[:200]}


def existing_records() -> dict[tuple[str, str], dict[str, Any]]:
    records = {}
    for path in source_files():
        source = load_yaml(path)
        for entry in source["entries"]:
            host = (urllib.parse.urlsplit(entry["canonical_url"]).hostname or "").removeprefix("www.")
            records[(source["category"], host)] = {
                "category": source["category"],
                "host": host,
                "url": entry["canonical_url"],
                "direct_queries": ["existing reviewed pilot"],
                "track_hints": {source["track"]: 100},
                "titles": [entry["name"]],
                "snippets": [entry["reason"]],
                "citations": entry["evidence_urls"],
                "discovery_score": 500,
                "existing": entry,
                "existing_track": source["track"],
            }
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-category", type=int, default=360)
    parser.add_argument("--independent-boost", type=int, default=280)
    parser.add_argument("--workers", type=int, default=32)
    args = parser.parse_args()

    candidates = json.loads((BUILD / "candidates.json").read_text(encoding="utf-8"))
    selected: dict[tuple[str, str], dict[str, Any]] = existing_records()
    counts: Counter[str] = Counter()
    for item in candidates:
        if counts[item["category"]] >= args.per_category:
            continue
        if item["host"] in GENERIC_HOSTS or "." not in item["host"]:
            continue
        if item["host"].startswith(("email.", "click.", "links.", "track.")):
            continue
        key = (item["category"], item["host"])
        selected.setdefault(key, item)
        counts[item["category"]] += 1

    independent_counts: Counter[str] = Counter()
    for item in candidates:
        if independent_counts[item["category"]] >= args.independent_boost:
            continue
        if item["host"] in GENERIC_HOSTS or "." not in item["host"]:
            continue
        hints = item.get("track_hints", {})
        if int(hints.get("independent", 0)) <= int(hints.get("publisher_company", 0)):
            continue
        if item["host"].startswith(("email.", "click.", "links.", "track.")):
            continue
        selected.setdefault((item["category"], item["host"]), item)
        independent_counts[item["category"]] += 1

    records = sorted(selected.values(), key=lambda item: (item["category"], -item["discovery_score"], item["host"]))
    previous_path = BUILD / "enriched.json"
    previous = {}
    if previous_path.exists():
        previous = {
            (item["category"], item["host"]): item
            for item in json.loads(previous_path.read_text(encoding="utf-8"))
        }
    pending = [item for item in records if (item["category"], item["host"]) not in previous]
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        fetched = list(executor.map(fetch, pending))
    enriched = []
    for record in records:
        key = (record["category"], record["host"])
        item = previous.get(key)
        if item is None:
            item = fetched.pop(0)
        else:
            item = {**record, **item}
        if item.get("accepted"):
            item["track"], item["track_confidence"] = classify_track(item, item.get("schema", {}))
        enriched.append(item)
    enriched.sort(key=lambda item: (item["category"], not item["accepted"], -item["discovery_score"], item["host"]))
    (BUILD / "enriched.json").write_text(json.dumps(enriched, indent=2) + "\n", encoding="utf-8")

    summary = defaultdict(lambda: {"fetched": 0, "accepted": 0, "independent": 0, "publisher_company": 0})
    for item in enriched:
        category = item["category"]
        summary[category]["fetched"] += 1
        if item["accepted"]:
            summary[category]["accepted"] += 1
            summary[category][item["track"]] += 1
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
