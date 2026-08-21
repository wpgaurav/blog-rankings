#!/usr/bin/env python3
"""Collect About-page ownership signals and current feed dates for finalists."""

from __future__ import annotations

import argparse
import email.utils
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from common import ROOT, load_yaml


BUILD = ROOT / "build" / "discovery"
USER_AGENT = "Gatilab-Blog-Rankings-Research/0.2 (+https://github.com/wpgaurav/blog-rankings)"
ABOUT_LABEL = re.compile(r"(?i)\b(about|our story|who we are|team|masthead|editorial team|contributors?)\b")
INDEPENDENT_TERMS = re.compile(r"(?i)\b(i am|i'm|i have|my name|my blog|written by me|independent writer|solo writer|one-person|one person|husband and wife|family-run|founder-led)\b")
PUBLISHER_TERMS = re.compile(r"(?i)\b(our team|editorial team|newsroom|staff writers?|our editors?|owned by|a division of|our company|media company|publishing company|contributors|editorial board)\b")
DATE_PATTERNS = [
    re.compile(r"<pubDate[^>]*>(.*?)</pubDate>", re.I | re.S),
    re.compile(r"<updated[^>]*>(.*?)</updated>", re.I | re.S),
    re.compile(r"<published[^>]*>(.*?)</published>", re.I | re.S),
    re.compile(r'(?i)(?:datePublished|dateModified)"?\s*:\s*"([0-9]{4}-[0-9]{2}-[0-9]{2}[^"<]*)'),
    re.compile(r"<time[^>]+datetime=[\"']([^\"']+)", re.I),
]


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str, str]] = []
        self.text_parts: list[str] = []
        self.anchor_href: str | None = None
        self.anchor_title = ""
        self.anchor_text: list[str] = []
        self.feed_url: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): value or "" for key, value in attrs}
        lower = tag.lower()
        if lower == "a" and attributes.get("href"):
            self.anchor_href = attributes["href"]
            self.anchor_title = attributes.get("title", "")
            self.anchor_text = []
        elif lower == "link":
            rel = set(attributes.get("rel", "").lower().split())
            if "alternate" in rel and attributes.get("type", "").lower() in {"application/rss+xml", "application/atom+xml"}:
                self.feed_url = attributes.get("href")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self.anchor_href:
            self.links.append((self.anchor_href, " ".join(self.anchor_text), self.anchor_title))
            self.anchor_href = None
            self.anchor_title = ""
            self.anchor_text = []

    def handle_data(self, data: str) -> None:
        value = re.sub(r"\s+", " ", data).strip()
        if not value:
            return
        self.text_parts.append(value)
        if self.anchor_href:
            self.anchor_text.append(value)


def fetch(url: str, limit: int = 1_500_000) -> tuple[int | None, str | None, bytes, str | None]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xml,text/xml,*/*;q=0.8"})
    try:
        with urllib.request.urlopen(request, timeout=15, context=ssl.create_default_context()) as response:
            return response.status, response.geturl(), response.read(limit), response.headers.get_content_charset()
    except urllib.error.HTTPError as error:
        return error.code, error.geturl(), b"", None
    except Exception:
        return None, None, b"", None


def parse_date(value: str) -> datetime | None:
    cleaned = re.sub(r"<!\[CDATA\[|\]\]>", "", value).strip()
    try:
        parsed = email.utils.parsedate_to_datetime(cleaned)
        if parsed:
            return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        pass
    try:
        parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def latest_date(body: str) -> str | None:
    dates = []
    for pattern in DATE_PATTERNS:
        for match in pattern.findall(body)[:30]:
            parsed = parse_date(re.sub(r"<[^>]+>", "", match))
            if parsed and 2000 <= parsed.year <= 2027:
                dates.append(parsed)
    return max(dates).date().isoformat() if dates else None


def inspect(site: dict[str, Any]) -> dict[str, Any]:
    canonical = site["url"]
    status, final_url, body, charset = fetch(canonical)
    if not body or not final_url:
        return {**site, "status": status, "ownership": "unknown", "latest_date": None}
    html = body.decode(charset or "utf-8", errors="replace")
    parser = PageParser()
    parser.feed(html)
    source_host = (urllib.parse.urlsplit(final_url).hostname or "").removeprefix("www.")
    about_url = None
    for href, text, title in parser.links:
        candidate = urllib.parse.urljoin(final_url, href)
        candidate_host = (urllib.parse.urlsplit(candidate).hostname or "").removeprefix("www.")
        if candidate_host == source_host and ABOUT_LABEL.search(f"{text} {title} {urllib.parse.urlsplit(candidate).path}"):
            about_url = candidate
            break

    about_text = ""
    if about_url:
        about_status, about_final, about_body, about_charset = fetch(about_url, 800_000)
        if about_body and about_status and about_status < 400:
            about_parser = PageParser()
            about_parser.feed(about_body.decode(about_charset or "utf-8", errors="replace"))
            about_text = " ".join(about_parser.text_parts)[:80_000]

    combined = " ".join([" ".join(parser.text_parts)[:30_000], about_text])
    independent_hits = len(INDEPENDENT_TERMS.findall(combined))
    publisher_hits = len(PUBLISHER_TERMS.findall(combined))
    if independent_hits > publisher_hits and independent_hits > 0:
        ownership = "independent"
    elif publisher_hits > independent_hits and publisher_hits > 0:
        ownership = "publisher_company"
    else:
        ownership = "unknown"

    feed_url = urllib.parse.urljoin(final_url, parser.feed_url) if parser.feed_url else site.get("feed_url")
    date_value = latest_date(html)
    if feed_url:
        feed_status, _, feed_body, feed_charset = fetch(feed_url, 1_000_000)
        if feed_body and feed_status and feed_status < 400:
            feed_date = latest_date(feed_body.decode(feed_charset or "utf-8", errors="replace"))
            if feed_date and (not date_value or feed_date > date_value):
                date_value = feed_date

    return {
        **site,
        "status": status,
        "final_url": final_url,
        "about_url": about_url,
        "feed_url": feed_url,
        "ownership": ownership,
        "independent_terms": independent_hits,
        "publisher_terms": publisher_hits,
        "latest_date": date_value,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=ROOT / "build" / "final-sources")
    parser.add_argument("--workers", type=int, default=40)
    args = parser.parse_args()

    sites: dict[str, dict[str, Any]] = {}
    enriched = {
        item["host"]: item
        for item in json.loads((BUILD / "enriched.json").read_text(encoding="utf-8"))
    }
    for path in args.source.glob("*/*/*.yml"):
        for entry in load_yaml(path)["entries"]:
            host = (urllib.parse.urlsplit(entry["canonical_url"]).hostname or "").removeprefix("www.")
            item = enriched.get(host, {})
            sites.setdefault(
                host,
                {
                    "host": host,
                    "url": entry["canonical_url"],
                    "feed_url": item.get("feed_url"),
                },
            )
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        profiles = list(executor.map(inspect, sorted(sites.values(), key=lambda item: item["host"])))
    profiles.sort(key=lambda item: item["host"])
    output = BUILD / "profiles.json"
    output.write_text(json.dumps({item["host"]: item for item in profiles}, indent=2) + "\n", encoding="utf-8")
    summary = {
        "sites": len(profiles),
        "independent": sum(item["ownership"] == "independent" for item in profiles),
        "publisher_company": sum(item["ownership"] == "publisher_company" for item in profiles),
        "unknown": sum(item["ownership"] == "unknown" for item in profiles),
        "fresh_within_180_days": sum(bool(item["latest_date"] and item["latest_date"] >= "2026-02-22") for item in profiles),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
