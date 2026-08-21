#!/usr/bin/env python3
"""Audit complete draft sources before they replace the public data tree."""

from __future__ import annotations

import argparse
import json
import re
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from common import ROOT, SOURCE_SCHEMA, RankingsError, load_yaml, validate_document, weighted_score


GENERIC_NAME = re.compile(r"(?i)^(home|homepage|blog|official site|welcome|front page|about me)$")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=ROOT / "build" / "final-sources")
    args = parser.parse_args()

    files = sorted(args.source.glob("*/*/*.yml"))
    if len(files) != 20:
        raise RankingsError(f"Expected 20 final source files, found {len(files)}")
    appearances: Counter[str] = Counter()
    category_domains: defaultdict[str, set[str]] = defaultdict(set)
    top_rows: list[dict[str, Any]] = []
    issues: list[str] = []
    overrides = load_yaml(ROOT / "data" / "editorial-overrides.yml")["categories"]

    for path in files:
        source = load_yaml(path)
        validate_document(source, SOURCE_SCHEMA, str(path))
        if source["status"] != "final" or len(source["entries"]) != 100:
            issues.append(f"{path}: final lists require 100 entries")
        ranked = sorted(source["entries"], key=lambda entry: (-weighted_score(entry["scores"]), entry["name"].casefold()))
        ranked_hosts = [
            (urllib.parse.urlsplit(entry["canonical_url"]).hostname or "").removeprefix("www.")
            for entry in ranked[:10]
        ]
        expected_hosts = overrides[source["category"]][source["track"]]
        if ranked_hosts != expected_hosts:
            issues.append(
                f"{source['category']}/{source['track']}: Top 10 differs from editorial override"
            )
        for entry in ranked:
            host = re.sub(r"^www\.", "", re.sub(r"^https?://", "", entry["canonical_url"]).split("/", 1)[0])
            appearances[host] += 1
            if host in category_domains[source["category"]]:
                issues.append(f"{source['category']}: duplicate host {host}")
            category_domains[source["category"]].add(host)
            if GENERIC_NAME.match(entry["name"]):
                issues.append(f"{path}: generic name {entry['name']} for {host}")
        for rank, entry in enumerate(ranked[:25], start=1):
            top_rows.append(
                {
                    "category": source["category"],
                    "track": source["track"],
                    "rank": rank,
                    "score": weighted_score(entry["scores"]),
                    "name": entry["name"],
                    "url": entry["canonical_url"],
                    "confidence": entry["confidence"],
                    "best_for": entry["best_for"],
                }
            )

    for host, count in appearances.items():
        if count > 2:
            issues.append(f"{host}: appears in {count} categories")
    report = {
        "files": len(files),
        "entries": sum(len(load_yaml(path)["entries"]) for path in files),
        "unique_hosts": len(appearances),
        "max_categories_per_host": max(appearances.values()),
        "top25_provisional": sum(1 for row in top_rows if row["confidence"] == "provisional"),
        "issues": issues,
        "top25": top_rows,
    }
    output = ROOT / "build" / "final-audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "top25"}, indent=2))
    if issues:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
