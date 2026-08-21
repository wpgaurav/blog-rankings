#!/usr/bin/env python3
"""Validate ranking sources and generated public artifacts."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from common import (
    ROOT,
    SOURCE_SCHEMA,
    WEB_SCHEMA,
    RankingsError,
    canonical_domain,
    categories,
    load_json,
    load_yaml,
    source_files,
    validate_document,
)


NOFOLLOW_LINK = re.compile(r'<a\s+href="https://[^\"]+"\s+rel="nofollow noopener">')


def validate_sources() -> None:
    known = categories()
    id_categories: defaultdict[str, set[str]] = defaultdict(set)
    category_ids: defaultdict[str, set[str]] = defaultdict(set)
    for path in source_files():
        source = load_yaml(path)
        validate_document(source, SOURCE_SCHEMA, str(path.relative_to(ROOT)))
        if source["category"] not in known:
            raise RankingsError(f"{path}: unknown category")
        for entry in source["entries"]:
            if entry["id"] in category_ids[source["category"]]:
                raise RankingsError(f"duplicate publication id inside {source['category']}: {entry['id']}")
            category_ids[source["category"]].add(entry["id"])
            id_categories[entry["id"]].add(source["category"])
    for publication_id, publication_categories in id_categories.items():
        if len(publication_categories) > 2:
            raise RankingsError(
                f"publication appears in more than two categories: {publication_id} ({len(publication_categories)})"
            )


def validate_generated() -> None:
    payloads = sorted((ROOT / "dist" / "web" / "latest").glob("*.json"))
    category_payloads = [path for path in payloads if path.name != "index.json"]
    if not category_payloads:
        raise RankingsError("no generated category payloads found")
    for path in category_payloads:
        data = load_json(path)
        validate_document(data, WEB_SCHEMA, str(path.relative_to(ROOT)))
        for track in ("independent", "publisher_company"):
            items = data["tracks"][track]["items"]
            if len(items) != 10:
                raise RankingsError(f"{path}: web payload must expose exactly 10 {track} items")
            ranks = [item["rank"] for item in items]
            if ranks != list(range(1, 11)):
                raise RankingsError(f"{path}: {track} ranks are not 1 through 10")
            domains = [canonical_domain(item["url"]) for item in items]
            if len(domains) != len(set(domains)):
                raise RankingsError(f"{path}: duplicate domain in {track}")

    for path in sorted((ROOT / "dist" / "markdown").glob("*/*/*.md")):
        text = path.read_text(encoding="utf-8")
        links = [line for line in text.splitlines() if "<a href=" in line]
        if not links or any(not NOFOLLOW_LINK.search(line) for line in links):
            raise RankingsError(f"{path}: ranked links must use rel=\"nofollow noopener\"")

    index = load_json(ROOT / "dist" / "web" / "latest" / "index.json")
    if len(index.get("categories", [])) != len(category_payloads):
        raise RankingsError("index category count does not match generated category payloads")


def validate_privacy() -> None:
    forbidden = re.compile(r"(?i)(application_password|root_password|private[_ -]?key|signed[_ -]?url)")
    for root in (ROOT / "data", ROOT / "dist"):
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in {".yml", ".yaml", ".json", ".md"}:
                if forbidden.search(path.read_text(encoding="utf-8")):
                    raise RankingsError(f"{path}: possible private operational data")


def main() -> None:
    validate_sources()
    validate_generated()
    validate_privacy()
    print("Gatilab Blog Rankings validation passed.")


if __name__ == "__main__":
    try:
        main()
    except RankingsError as error:
        raise SystemExit(str(error)) from error
