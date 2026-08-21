#!/usr/bin/env python3
"""Collect current reach and backlink-rank estimates for accepted candidates."""

from __future__ import annotations

import base64
import json
import urllib.request
from pathlib import Path
from typing import Any

from common import ROOT


BUILD = ROOT / "build" / "discovery"
TRAFFIC_URL = "https://api.dataforseo.com/v3/dataforseo_labs/google/bulk_traffic_estimation/live"
RANK_URL = "https://api.dataforseo.com/v3/backlinks/bulk_ranks/live"


def credentials() -> str:
    values: dict[str, str] = {}
    for raw_line in (Path.home() / ".env").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() in {"DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD"}:
            values[key.strip()] = value.strip().strip("'\"")
    return base64.b64encode(f"{values['DATAFORSEO_LOGIN']}:{values['DATAFORSEO_PASSWORD']}".encode()).decode()


def post(url: str, task: dict[str, Any], token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps([task]).encode(),
        headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.loads(response.read())


def chunks(items: list[str], size: int = 1000) -> list[list[str]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def result_items(response: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = response.get("tasks") or []
    results = tasks[0].get("result") or [] if tasks else []
    if not results:
        return []
    if isinstance(results[0], dict) and isinstance(results[0].get("items"), list):
        return results[0]["items"]
    return [item for item in results if isinstance(item, dict)]


def organic_etv(item: dict[str, Any]) -> float:
    metrics = item.get("metrics") or {}
    organic = metrics.get("organic") or {}
    value = organic.get("etv")
    if value is None:
        value = item.get("organic_etv") or item.get("etv") or 0
    return round(float(value or 0), 2)


def main() -> None:
    enriched = json.loads((BUILD / "enriched.json").read_text(encoding="utf-8"))
    hosts = sorted({item["host"] for item in enriched if item.get("accepted")})
    token = credentials()
    raw_dir = BUILD / "metrics-raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    traffic: dict[str, float] = {}
    ranks: dict[str, int] = {}
    for index, group in enumerate(chunks(hosts)):
        traffic_response = post(
            TRAFFIC_URL,
            {
                "targets": group,
                "location_code": 2840,
                "language_code": "en",
                "item_types": ["organic"],
                "tag": f"gbr-traffic-{index}",
            },
            token,
        )
        (raw_dir / f"traffic-{index}.json").write_text(json.dumps(traffic_response, indent=2) + "\n", encoding="utf-8")
        for item in result_items(traffic_response):
            target = str(item.get("target") or item.get("domain") or "").removeprefix("www.")
            if target:
                traffic[target] = organic_etv(item)

        rank_response = post(RANK_URL, {"targets": group, "tag": f"gbr-ranks-{index}"}, token)
        (raw_dir / f"ranks-{index}.json").write_text(json.dumps(rank_response, indent=2) + "\n", encoding="utf-8")
        for item in result_items(rank_response):
            target = str(item.get("target") or item.get("domain") or "").removeprefix("www.")
            if target:
                ranks[target] = int(item.get("rank") or 0)

    output = {
        "checked_hosts": len(hosts),
        "traffic_found": len(traffic),
        "ranks_found": len(ranks),
        "metrics": {
            host: {"organic_etv_us": traffic.get(host, 0), "backlink_rank": ranks.get(host, 0)}
            for host in hosts
        },
    }
    (BUILD / "metrics.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in output.items() if key != "metrics"}, indent=2))


if __name__ == "__main__":
    main()
