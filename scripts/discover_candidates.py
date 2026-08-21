#!/usr/bin/env python3
"""Discover category candidates from current SERPs and cited roundup links."""

from __future__ import annotations

import argparse
import base64
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


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build" / "discovery"
API_URL = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
USER_AGENT = "Gatilab-Blog-Rankings-Research/0.2 (+https://github.com/wpgaurav/blog-rankings)"
EXCLUDED_HOSTS = {
    "google.com", "bing.com", "yahoo.com", "duckduckgo.com", "youtube.com",
    "facebook.com", "instagram.com", "linkedin.com", "pinterest.com", "reddit.com",
    "x.com", "twitter.com", "tiktok.com", "wikipedia.org", "amazon.com", "quora.com",
    "feedspot.com", "bloggers.feedspot.com", "blog.feedspot.com", "bloglovin.com",
    "alltop.com", "blogarama.com", "ontoplist.com", "bloggerspassion.com",
}
ROUNDUP_WORDS = re.compile(r"(?i)\b(best|top|blogs?|bloggers?|publications?|newsletters?|follow|sites?)\b")


CATEGORY_QUERIES: dict[str, list[tuple[str, str]]] = {
    "technology": [
        ("best technology blogs", "publisher_company"),
        ("top tech blogs to follow", "publisher_company"),
        ("best independent technology blogs", "independent"),
        ("best software engineering blogs", "independent"),
        ("best cybersecurity blogs", "publisher_company"),
        ("best artificial intelligence blogs", "publisher_company"),
        ("best WordPress blogs", "publisher_company"),
        ("best consumer technology blogs", "publisher_company"),
        ("independent tech newsletters", "independent"),
        ("personal technology blogs worth reading", "independent"),
    ],
    "business": [
        ("best business blogs", "publisher_company"),
        ("top entrepreneurship blogs", "publisher_company"),
        ("best independent business blogs", "independent"),
        ("best startup blogs", "publisher_company"),
        ("best SaaS blogs", "publisher_company"),
        ("best leadership blogs", "publisher_company"),
        ("best small business blogs", "publisher_company"),
        ("founder blogs worth reading", "independent"),
        ("independent entrepreneur newsletters", "independent"),
        ("creator business blogs", "independent"),
    ],
    "marketing-seo": [
        ("best marketing blogs", "publisher_company"),
        ("best SEO blogs", "publisher_company"),
        ("best independent marketing blogs", "independent"),
        ("best content marketing blogs", "publisher_company"),
        ("best copywriting blogs", "publisher_company"),
        ("best social media marketing blogs", "publisher_company"),
        ("best analytics blogs for marketers", "publisher_company"),
        ("independent SEO newsletters", "independent"),
        ("marketing consultant blogs worth reading", "independent"),
        ("growth marketing newsletters", "independent"),
    ],
    "personal-finance": [
        ("best personal finance blogs", "publisher_company"),
        ("top money blogs", "publisher_company"),
        ("best independent personal finance blogs", "independent"),
        ("best investing blogs", "publisher_company"),
        ("best financial independence blogs", "independent"),
        ("best debt payoff blogs", "independent"),
        ("best tax blogs for individuals", "publisher_company"),
        ("personal finance newsletters to follow", "independent"),
        ("money bloggers worth reading", "independent"),
        ("best family finance blogs", "independent"),
    ],
    "science": [
        ("best science blogs", "publisher_company"),
        ("top science blogs to follow", "publisher_company"),
        ("best independent science blogs", "independent"),
        ("best space science blogs", "publisher_company"),
        ("best physics blogs", "independent"),
        ("best biology blogs", "publisher_company"),
        ("best climate science blogs", "publisher_company"),
        ("scientist blogs worth reading", "independent"),
        ("independent research newsletters", "independent"),
        ("best science communication blogs", "independent"),
    ],
    "education": [
        ("best education blogs", "publisher_company"),
        ("top teaching blogs", "publisher_company"),
        ("best independent education blogs", "independent"),
        ("best teacher blogs", "independent"),
        ("best higher education blogs", "publisher_company"),
        ("best learning science blogs", "publisher_company"),
        ("best study skills blogs", "independent"),
        ("education newsletters to follow", "independent"),
        ("professor blogs worth reading", "independent"),
        ("best edtech blogs", "publisher_company"),
    ],
    "health": [
        ("best health blogs", "publisher_company"),
        ("top wellness blogs", "publisher_company"),
        ("best independent health blogs", "independent"),
        ("best fitness blogs", "independent"),
        ("best nutrition blogs", "publisher_company"),
        ("best mental health blogs", "publisher_company"),
        ("best public health blogs", "publisher_company"),
        ("doctor blogs worth reading", "independent"),
        ("health newsletters to follow", "independent"),
        ("evidence based wellness blogs", "independent"),
    ],
    "travel": [
        ("best travel blogs", "publisher_company"),
        ("top travel blogs to follow", "publisher_company"),
        ("best independent travel blogs", "independent"),
        ("best solo travel blogs", "independent"),
        ("best family travel blogs", "independent"),
        ("best budget travel blogs", "independent"),
        ("best luxury travel blogs", "publisher_company"),
        ("travel newsletters to follow", "independent"),
        ("travel writer blogs worth reading", "independent"),
        ("best destination travel publications", "publisher_company"),
    ],
    "food": [
        ("best food blogs", "publisher_company"),
        ("top recipe blogs", "publisher_company"),
        ("best independent food blogs", "independent"),
        ("best baking blogs", "independent"),
        ("best healthy recipe blogs", "independent"),
        ("best restaurant blogs", "publisher_company"),
        ("best food science blogs", "publisher_company"),
        ("food newsletters to follow", "independent"),
        ("chef blogs worth reading", "independent"),
        ("best culinary publications", "publisher_company"),
    ],
    "culture-entertainment": [
        ("best culture blogs", "publisher_company"),
        ("best entertainment blogs", "publisher_company"),
        ("best independent culture blogs", "independent"),
        ("best book blogs", "independent"),
        ("best film blogs", "independent"),
        ("best music blogs", "publisher_company"),
        ("best gaming blogs", "publisher_company"),
        ("culture newsletters to follow", "independent"),
        ("independent criticism blogs", "independent"),
        ("best pop culture publications", "publisher_company"),
    ],
}


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(href)


def load_credentials() -> tuple[str, str]:
    values: dict[str, str] = {}
    for raw_line in (Path.home() / ".env").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() in {"DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD"}:
            values[key.strip()] = value.strip().strip("'\"")
    return values["DATAFORSEO_LOGIN"], values["DATAFORSEO_PASSWORD"]


def host(url: str) -> str:
    value = (urllib.parse.urlsplit(url).hostname or "").lower()
    return value[4:] if value.startswith("www.") else value


def excluded(url: str) -> bool:
    value = host(url)
    return not value or any(value == item or value.endswith("." + item) for item in EXCLUDED_HOSTS)


def normalize_url(url: str, base: str | None = None) -> str | None:
    try:
        absolute = urllib.parse.urljoin(base or url, url)
        parsed = urllib.parse.urlsplit(absolute)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    hostname = parsed.hostname.lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    path = parsed.path or "/"
    return urllib.parse.urlunsplit(("https", hostname, path, "", ""))


def dataforseo_task(task: dict[str, Any], token: str) -> dict[str, Any]:
    """Run one live SERP task because the endpoint rejects multi-task payloads."""
    request = urllib.request.Request(
        API_URL,
        data=json.dumps([task]).encode(),
        headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        data = json.loads(response.read())
    tasks = data.get("tasks") or []
    if not tasks:
        return {"status_code": 50000, "status_message": "No task returned", "result": None, "cost": 0}
    return tasks[0]


def dataforseo(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    login, password = load_credentials()
    token = base64.b64encode(f"{login}:{password}".encode()).decode()
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda task: dataforseo_task(task, token), tasks))
    return {"tasks": results, "cost": sum(float(task.get("cost") or 0) for task in results)}


def fetch_page(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20, context=ssl.create_default_context()) as response:
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                return {"url": url, "final_url": response.geturl(), "links": [], "status": response.status}
            body = response.read(2_000_000).decode(response.headers.get_content_charset() or "utf-8", errors="replace")
            parser = LinkParser()
            parser.feed(body)
            links = []
            source_host = host(response.geturl())
            for href in parser.links:
                candidate = normalize_url(href, response.geturl())
                if not candidate or excluded(candidate) or host(candidate) == source_host:
                    continue
                links.append(candidate)
            return {
                "url": url,
                "final_url": response.geturl(),
                "links": sorted(set(links)),
                "status": response.status,
            }
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        return {"url": url, "final_url": None, "links": [], "status": None, "error": str(error)[:200]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", choices=sorted(CATEGORY_QUERIES))
    parser.add_argument("--depth", type=int, default=100)
    parser.add_argument("--roundups-per-query", type=int, default=8)
    args = parser.parse_args()

    categories = [args.category] if args.category else sorted(CATEGORY_QUERIES)
    query_meta: list[dict[str, str]] = []
    tasks = []
    for category in categories:
        for keyword, track in CATEGORY_QUERIES[category]:
            query_meta.append({"category": category, "keyword": keyword, "track": track})
            tasks.append(
                {
                    "keyword": keyword,
                    "location_code": 2840,
                    "language_code": "en",
                    "device": "desktop",
                    "os": "windows",
                    "depth": args.depth,
                }
            )

    response = dataforseo(tasks)
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / "serp.raw.json").write_text(json.dumps(response, indent=2) + "\n", encoding="utf-8")

    direct: dict[tuple[str, str], dict[str, Any]] = {}
    roundups: dict[str, dict[str, Any]] = {}
    task_results = response.get("tasks") or []
    for index, task in enumerate(task_results):
        if index >= len(query_meta):
            break
        meta = query_meta[index]
        results = task.get("result") or []
        items = results[0].get("items", []) if results else []
        roundup_count = 0
        for item in items:
            if item.get("type") != "organic" or not item.get("url"):
                continue
            url = normalize_url(item["url"])
            if not url or excluded(url):
                continue
            key = (meta["category"], host(url))
            record = direct.setdefault(
                key,
                {
                    "category": meta["category"],
                    "host": host(url),
                    "url": url,
                    "direct_queries": [],
                    "track_hints": Counter(),
                    "titles": [],
                    "snippets": [],
                    "citations": [],
                },
            )
            record["direct_queries"].append(meta["keyword"])
            record["track_hints"][meta["track"]] += 1
            if item.get("title"):
                record["titles"].append(item["title"])
            if item.get("description"):
                record["snippets"].append(item["description"])

            searchable = f"{item.get('title', '')} {item.get('description', '')} {url}"
            if roundup_count < args.roundups_per_query and ROUNDUP_WORDS.search(searchable):
                roundups.setdefault(url, {"url": url, "sources": []})["sources"].append(meta)
                roundup_count += 1

    with ThreadPoolExecutor(max_workers=16) as executor:
        fetched = list(executor.map(fetch_page, sorted(roundups)))
    fetched_by_url = {item["url"]: item for item in fetched}

    for roundup_url, roundup in roundups.items():
        fetched_roundup = fetched_by_url.get(roundup_url, {})
        for link in fetched_roundup.get("links", []):
            for meta in roundup["sources"]:
                key = (meta["category"], host(link))
                record = direct.setdefault(
                    key,
                    {
                        "category": meta["category"],
                        "host": host(link),
                        "url": link,
                        "direct_queries": [],
                        "track_hints": Counter(),
                        "titles": [],
                        "snippets": [],
                        "citations": [],
                    },
                )
                record["citations"].append(roundup_url)
                record["track_hints"][meta["track"]] += 1

    output = []
    for record in direct.values():
        record["direct_queries"] = sorted(set(record["direct_queries"]))
        record["citations"] = sorted(set(record["citations"]))
        record["titles"] = list(dict.fromkeys(record["titles"]))[:5]
        record["snippets"] = list(dict.fromkeys(record["snippets"]))[:5]
        record["track_hints"] = dict(record["track_hints"])
        record["discovery_score"] = (
            len(record["direct_queries"]) * 4
            + len(record["citations"]) * 3
            + sum(record["track_hints"].values())
        )
        output.append(record)
    output.sort(key=lambda item: (item["category"], -item["discovery_score"], item["host"]))
    (BUILD / "candidates.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")

    counts = defaultdict(lambda: {"candidates": 0, "independent_hints": 0, "publisher_hints": 0})
    for item in output:
        counts[item["category"]]["candidates"] += 1
        counts[item["category"]]["independent_hints"] += item["track_hints"].get("independent", 0)
        counts[item["category"]]["publisher_hints"] += item["track_hints"].get("publisher_company", 0)
    print(json.dumps(counts, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
