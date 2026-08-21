#!/usr/bin/env python3
"""Check current publication destinations without changing ranking data."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from common import ROOT, load_yaml, source_files


USER_AGENT = "Gatilab-Blog-Rankings-Link-Check/0.1 (+https://github.com/wpgaurav/blog-rankings)"


def check(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"},
        method="GET",
    )
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=20, context=context) as response:
            response.read(1024)
            return {"url": url, "status": response.status, "final_url": response.geturl(), "error": None}
    except urllib.error.HTTPError as error:
        return {"url": url, "status": error.code, "final_url": error.geturl(), "error": None}
    except Exception as error:  # Network errors are evidence for review, not automatic removal.
        return {"url": url, "status": None, "final_url": None, "error": str(error)[:240]}


def main() -> None:
    urls = set()
    for path in source_files():
        for entry in load_yaml(path)["entries"]:
            urls.add(entry["canonical_url"])
            urls.update(entry["evidence_urls"])
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = sorted(executor.map(check, sorted(urls)), key=lambda item: item["url"])
    report = {
        "checked": len(results),
        "ok_or_redirected": sum(1 for item in results if item["status"] and item["status"] < 400),
        "blocked_or_missing": sum(1 for item in results if item["status"] and item["status"] >= 400),
        "network_errors": sum(1 for item in results if item["error"]),
        "results": results,
    }
    output = ROOT / "build" / "link-check.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, indent=2))


if __name__ == "__main__":
    main()
