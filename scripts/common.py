#!/usr/bin/env python3
"""Shared build and validation helpers for Gatilab Blog Rankings."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import yaml
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SCHEMA = ROOT / "schema" / "ranking-source.schema.json"
WEB_SCHEMA = ROOT / "schema" / "web-payload.schema.json"
WEIGHTS = {
    "editorial_quality": 0.30,
    "trust": 0.20,
    "reach": 0.20,
    "freshness": 0.15,
    "ux": 0.10,
    "impact": 0.05,
}
TRACK_LABELS = {
    "independent": "Independent Blogs",
    "publisher_company": "Publisher and Company Blogs",
}


class RankingsError(RuntimeError):
    """Raised when source or generated ranking data violates the contract."""


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RankingsError(f"{path}: expected a YAML mapping")
    return normalize_yaml_scalars(data)


def normalize_yaml_scalars(value: Any) -> Any:
    """Convert PyYAML date scalars to the strings required by JSON Schema."""
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: normalize_yaml_scalars(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_yaml_scalars(item) for item in value]
    return value


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RankingsError(f"{path}: expected a JSON object")
    return data


def validator(path: Path) -> Draft202012Validator:
    return Draft202012Validator(load_json(path), format_checker=FormatChecker())


def validate_document(data: dict[str, Any], schema_path: Path, label: str) -> None:
    errors = sorted(validator(schema_path).iter_errors(data), key=lambda error: list(error.path))
    if not errors:
        return
    messages = []
    for error in errors:
        location = ".".join(str(part) for part in error.absolute_path) or "root"
        messages.append(f"{label}:{location}: {error.message}")
    raise RankingsError("\n".join(messages))


def categories() -> dict[str, dict[str, Any]]:
    data = load_yaml(ROOT / "categories.yml")
    items = data.get("categories", [])
    if not isinstance(items, list):
        raise RankingsError("categories.yml: categories must be a list")
    result = {item["slug"]: item for item in items}
    if len(result) != 10:
        raise RankingsError("categories.yml must define exactly 10 unique launch categories")
    return result


def source_files() -> list[Path]:
    return sorted((ROOT / "data" / "rankings").glob("*/*/*.yml"))


def canonical_domain(url: str) -> str:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def canonical_url(url: str) -> str:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") + "/"
    return urlunsplit(("https", host, path, "", ""))


def weighted_score(scores: dict[str, int]) -> float:
    missing = set(WEIGHTS) - set(scores)
    if missing:
        raise RankingsError(f"missing score components: {', '.join(sorted(missing))}")
    return round(sum(scores[key] * weight for key, weight in WEIGHTS.items()), 1)


def ranked_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for entry in entries:
        item = dict(entry)
        item["canonical_url"] = canonical_url(item["canonical_url"])
        item["score"] = weighted_score(item["scores"])
        ranked.append(item)
    ranked.sort(
        key=lambda item: (
            -item["score"],
            -item["scores"]["editorial_quality"],
            -item["scores"]["trust"],
            item["name"].casefold(),
        )
    )
    for position, item in enumerate(ranked, start=1):
        item["rank"] = position
        item["movement"] = "new"
    return ranked


def public_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "rank": entry["rank"],
        "id": entry["id"],
        "name": entry["name"],
        "url": entry["canonical_url"],
        "country": entry["country"],
        "score": entry["score"],
        "movement": entry["movement"],
        "best_for": entry["best_for"],
        "reason": entry["reason"],
        "limitation": entry["limitation"],
        "confidence": entry["confidence"],
        "reviewed_at": entry["reviewed_at"],
        "evidence_urls": entry["evidence_urls"],
    }


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
