#!/usr/bin/env python3
"""Build a complete 100-per-track draft for editorial review."""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import urllib.parse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from common import ROOT, categories, load_yaml, weighted_score


BUILD = ROOT / "build" / "discovery"
DEFAULT_OUTPUT = ROOT / "build" / "final-sources"
TRACKS = ("independent", "publisher_company")
INSTITUTIONAL_SUFFIXES = (".edu", ".gov", ".ac.uk", ".edu.au")
BAD_NAMES = {"home", "homepage", "official site", "welcome", "blog", "medium", "wordpress.com", "about me", "front page"}
FIRST_PERSON = re.compile(r"(?i)\b(i|my|me|one teacher|written by|personal blog|i'm|i’ve|i've)\b")
COMMERCIAL = re.compile(r"(?i)\b(pricing|customers|our product|book a|free trial|software platform|services|shop|buy now)\b")
ACCESS = re.compile(r"(?i)\b(subscribe|subscription|members?|paywall|premium|register|sign in)\b")

SUBTOPICS: dict[str, list[tuple[set[str], str]]] = {
    "technology": [
        ({"cybersecurity", "security", "privacy"}, "security, privacy, and cyber risk"),
        ({"software", "developer", "engineering", "programming"}, "software engineering and developer practice"),
        ({"ai", "artificial intelligence", "machine learning"}, "AI systems and their practical consequences"),
        ({"wordpress", "cms"}, "WordPress publishing and development"),
        ({"gadgets", "devices", "consumer technology"}, "devices and consumer technology"),
    ],
    "business": [
        ({"saas", "software as a service"}, "SaaS growth and operating decisions"),
        ({"startup", "founder", "venture"}, "startups, founders, and company building"),
        ({"leadership", "management", "teams"}, "leadership, management, and organizational work"),
        ({"small business", "entrepreneur"}, "small-business and entrepreneurial practice"),
    ],
    "marketing-seo": [
        ({"seo", "search"}, "SEO and search-led growth"),
        ({"copywriting", "copywriter", "writing"}, "copywriting and persuasive communication"),
        ({"content marketing", "content strategy"}, "content strategy and distribution"),
        ({"social media", "social marketing"}, "social-media strategy and publishing"),
        ({"analytics", "conversion", "cro"}, "analytics, experimentation, and conversion"),
    ],
    "personal-finance": [
        ({"investing", "investment", "portfolio"}, "investing and long-term wealth decisions"),
        ({"financial independence", "fire", "early retirement"}, "financial independence and early retirement"),
        ({"debt", "credit"}, "debt, credit, and financial recovery"),
        ({"budget", "saving", "frugal"}, "budgeting, saving, and practical money habits"),
        ({"tax", "retirement"}, "tax and retirement planning"),
    ],
    "science": [
        ({"space", "astronomy", "nasa"}, "space, astronomy, and exploration"),
        ({"physics", "quantum"}, "physics and the mechanisms behind new research"),
        ({"biology", "life science", "biotech"}, "biology, biotechnology, and life science"),
        ({"climate", "environment"}, "climate and environmental science"),
        ({"research", "scientific"}, "research findings and science communication"),
    ],
    "education": [
        ({"teacher", "teaching", "classroom"}, "classroom teaching and educator practice"),
        ({"higher education", "university", "college"}, "higher education and academic work"),
        ({"learning science", "cognitive", "study"}, "learning science and study practice"),
        ({"edtech", "education technology"}, "education technology and digital learning"),
    ],
    "health": [
        ({"mental health", "psychology"}, "mental health and psychological wellbeing"),
        ({"fitness", "exercise", "training"}, "fitness, exercise, and sustainable training"),
        ({"nutrition", "diet"}, "nutrition and evidence-aware food decisions"),
        ({"medical", "medicine", "doctor"}, "medicine and patient-facing health education"),
        ({"public health"}, "public health and healthcare systems"),
    ],
    "travel": [
        ({"solo travel", "solo"}, "solo travel and independent trip planning"),
        ({"family travel", "family"}, "family travel and practical itineraries"),
        ({"budget travel", "backpacking", "budget"}, "budget travel and long-term exploration"),
        ({"luxury travel", "luxury"}, "luxury travel and destination experiences"),
        ({"adventure", "outdoors"}, "adventure travel and outdoor destinations"),
    ],
    "food": [
        ({"baking", "bread", "pastry"}, "baking, pastry, and dependable technique"),
        ({"healthy", "nutrition", "plant based", "vegan"}, "health-aware recipes and practical cooking"),
        ({"restaurant", "dining", "chef"}, "restaurants, chefs, and food culture"),
        ({"food science", "technique"}, "culinary technique and food science"),
        ({"recipe", "cooking", "kitchen"}, "tested recipes and everyday cooking"),
    ],
    "culture-entertainment": [
        ({"books", "book", "literature"}, "books, literature, and reading culture"),
        ({"film", "movies", "cinema"}, "film criticism and cinema culture"),
        ({"music", "album"}, "music criticism, discovery, and industry context"),
        ({"gaming", "games", "video game"}, "games, criticism, and gaming culture"),
        ({"television", "tv", "entertainment"}, "television and popular entertainment"),
    ],
}

DEFAULT_BEST_FOR = {
    "technology": "technology reporting and practical analysis",
    "business": "business building and entrepreneurial judgment",
    "marketing-seo": "marketing strategy and audience growth",
    "personal-finance": "practical personal-finance decisions",
    "science": "science reporting and research communication",
    "education": "teaching, learning, and education practice",
    "health": "health education and sustainable wellbeing",
    "travel": "travel planning and destination insight",
    "food": "recipes, technique, and food culture",
    "culture-entertainment": "culture, criticism, and entertainment analysis",
}


def clamp(value: float, minimum: int = 0, maximum: int = 100) -> int:
    return int(round(max(minimum, min(maximum, value))))


def percentile(value: float, values: list[float]) -> float:
    if not values:
        return 0.0
    lower = sum(1 for candidate in values if candidate < value)
    equal = sum(1 for candidate in values if candidate == value)
    return (lower + equal * 0.5) / len(values)


def country_from_host(host: str) -> str:
    mapping = {
        ".co.uk": "GB", ".uk": "GB", ".ca": "CA", ".com.au": "AU", ".au": "AU",
        ".co.nz": "NZ", ".nz": "NZ", ".in": "IN", ".ie": "IE", ".de": "DE",
        ".fr": "FR", ".es": "ES", ".it": "IT", ".nl": "NL", ".sg": "SG",
        ".za": "ZA", ".jp": "JP", ".se": "SE", ".no": "NO", ".dk": "DK",
    }
    for suffix, country in mapping.items():
        if host.endswith(suffix):
            return country
    return "XX"


def publication_name(item: dict[str, Any]) -> str:
    if item.get("curated_name"):
        return str(item["curated_name"])
    existing = item.get("existing") or {}
    if existing.get("name"):
        return existing["name"]
    name = re.sub(r"(?i)\b(right arrow|left arrow|menu|logo)\b", " ", item.get("name") or "")
    name = re.sub(r"\s+", " ", name).strip(" |-:")
    repeated = any(name.lower().split().count(word) > 3 for word in set(name.lower().split()))
    if name.casefold() in BAD_NAMES or len(name) < 2 or len(name) > 70 or repeated:
        labels = item["host"].split(".")
        label = labels[0]
        if label in {"blog", "blogs", "news", "www", "web"} and len(labels) > 1:
            label = labels[1]
        name = label.replace("-", " ").title()
    return name[:120]


def topic_text(item: dict[str, Any]) -> str:
    return " ".join(
        [
            item.get("title") or "",
            item.get("description") or "",
            " ".join(item.get("titles") or []),
            " ".join(item.get("snippets") or []),
            " ".join(item.get("direct_queries") or []),
        ]
    ).lower()


def best_for(item: dict[str, Any]) -> str:
    existing = item.get("existing") or {}
    if existing.get("best_for"):
        return existing["best_for"]
    text = topic_text(item)
    for words, phrase in SUBTOPICS[item["category"]]:
        if any(word in text for word in words):
            return phrase
    return DEFAULT_BEST_FOR[item["category"]]


def reason(item: dict[str, Any], topic: str) -> str:
    existing = item.get("existing") or {}
    if existing.get("reason"):
        return existing["reason"]
    name = publication_name(item)
    signals = []
    if item.get("feed_url"):
        signals.append("a discoverable feed")
    if item.get("schema", {}).get("article") or item.get("article_count"):
        signals.append("a visible article archive")
    if item.get("trust_signals", {}).get("authors"):
        signals.append("named authorship")
    if item.get("trust_signals", {}).get("about"):
        signals.append("clear ownership context")
    if not signals:
        signals.append("a clearly defined editorial focus")
    joined = ", ".join(signals[:2])
    value = f"{name} concentrates on {topic}, with {joined} that makes its current publishing work easier to evaluate."
    if len(value) > 280:
        value = value[:276].rsplit(" ", 1)[0] + "."
    return value


def limitation(item: dict[str, Any]) -> str:
    existing = item.get("existing") or {}
    if existing.get("limitation"):
        return existing["limitation"]
    description = item.get("description") or ""
    profile = item.get("profile") or {}
    if profile.get("latest_date") and profile["latest_date"] < "2026-02-22":
        return "The latest parseable public date is older than the normal 180-day activity window, so its status needs closer review."
    if ACCESS.search(description):
        return "Some complete material may require registration, membership, or a paid subscription."
    if not item.get("feed_url"):
        return "Publishing cadence is harder to verify because the site does not expose a discoverable RSS or Atom feed."
    trust_count = sum(bool(value) for value in item.get("trust_signals", {}).values())
    if trust_count < 2:
        return "Authorship and editorial-policy information is less visible than on higher-ranked publications."
    if int(item.get("html_bytes") or 0) > 1_000_000:
        return "The homepage is heavier and more commercially layered than a focused reading experience."
    return "Its broad subject range can make depth and usefulness uneven across individual topics."


def track_likelihood(item: dict[str, Any], track: str) -> float:
    hints = item.get("track_hints", {})
    independent = float(hints.get("independent", 0))
    publisher = float(hints.get("publisher_company", 0))
    total = independent + publisher or 1
    schema = item.get("schema", {})
    description = item.get("description") or ""
    institutional = item["host"].endswith(INSTITUTIONAL_SUFFIXES)
    existing_track = item.get("existing_track")
    curated_track = item.get("curated_track")
    ownership = (item.get("profile") or {}).get("ownership")
    metric = item.get("metric") or {}
    if track == "independent":
        score = 50 * independent / total
        score += 35 if schema.get("person") else 0
        score += 18 if FIRST_PERSON.search(description) else 0
        score += 22 if item["host"].endswith(".substack.com") else 0
        score -= 100 if institutional else 0
        score -= 28 if schema.get("organization") and not schema.get("person") else 0
        score -= 14 if COMMERCIAL.search(description) else 0
    else:
        score = 50 * publisher / total
        score += 40 if institutional else 0
        score += 26 if schema.get("organization") and not schema.get("person") else 0
        score += 15 if COMMERCIAL.search(description) else 0
        score -= 20 if schema.get("person") and not schema.get("organization") else 0
        score -= 20 if item["host"].endswith(".substack.com") else 0
    if existing_track == track:
        score += 300
    elif existing_track:
        score -= 300
    if curated_track == track:
        score += 1000
    elif curated_track:
        score -= 1000
    if ownership == track:
        score += 220
    elif ownership in {"independent", "publisher_company"}:
        score -= 220
    if ownership == "unknown" and schema.get("organization") and not FIRST_PERSON.search(description):
        score += -65 if track == "independent" else 65
    if (
        ownership == "unknown"
        and float(metric.get("backlink_rank", 0)) >= 520
        and float(metric.get("organic_etv_us", 0)) >= 1_000_000
        and not FIRST_PERSON.search(description)
    ):
        score += -90 if track == "independent" else 90
    return score


def preliminary_scores(item: dict[str, Any], metric: dict[str, Any], category_items: list[dict[str, Any]]) -> dict[str, int]:
    if item.get("curated_position"):
        base = 100 - int(item["curated_position"])
        return {
            "editorial_quality": base,
            "trust": max(0, base - 1),
            "reach": max(0, base - 2),
            "freshness": max(0, base - 1),
            "ux": max(0, base - 2),
            "impact": max(0, base - 1),
        }
    existing = item.get("existing") or {}
    if existing.get("scores"):
        return {key: int(value) for key, value in existing["scores"].items()}
    traffic_values = [float(candidate["metric"].get("organic_etv_us", 0)) for candidate in category_items]
    rank_values = [float(candidate["metric"].get("backlink_rank", 0)) for candidate in category_items]
    citation_values = [float(len(candidate["item"].get("citations") or [])) for candidate in category_items]
    traffic_pct = percentile(float(metric.get("organic_etv_us", 0)), traffic_values)
    rank_pct = percentile(float(metric.get("backlink_rank", 0)), rank_values)
    citation_pct = percentile(float(len(item.get("citations") or [])), citation_values)
    trust_count = sum(bool(value) for value in item.get("trust_signals", {}).values())
    profile = item.get("profile") or {}
    editorial = 57 + min(16, item.get("category_relevance", 0) * 2) + min(10, len(item.get("citations") or []) * 2)
    editorial += 5 if item.get("feed_url") else 0
    editorial += 4 if item.get("schema", {}).get("article") or item.get("article_count") else 0
    trust = 50 + trust_count * 7 + (5 if item.get("schema", {}).get("person") or item.get("schema", {}).get("organization") else 0)
    trust += 6 if profile.get("about_url") else 0
    trust += 5 if profile.get("ownership") in {"independent", "publisher_company"} else 0
    reach = 38 + 62 * (traffic_pct * 0.65 + rank_pct * 0.35)
    latest = profile.get("latest_date")
    if latest:
        age = (datetime(2026, 8, 21, tzinfo=timezone.utc).date() - datetime.fromisoformat(latest).date()).days
        if age <= 30:
            freshness = 96
        elif age <= 90:
            freshness = 88
        elif age <= 180:
            freshness = 78
        elif age <= 365:
            freshness = 62
        else:
            freshness = 45
    else:
        freshness = 58 + (12 if item.get("feed_url") else 0) + (8 if item.get("article_count") else 0) + (5 if item.get("schema", {}).get("article") else 0)
    ux = 62 + (14 if item.get("viewport") else 0) + (8 if int(item.get("html_bytes") or 0) < 900_000 else 0)
    impact = 42 + 58 * (rank_pct * 0.7 + citation_pct * 0.3)
    scores = {
        "editorial_quality": clamp(editorial, 45, 96),
        "trust": clamp(trust, 45, 95),
        "reach": clamp(reach, 35, 98),
        "freshness": clamp(freshness, 45, 94),
        "ux": clamp(ux, 50, 90),
        "impact": clamp(impact, 35, 96),
    }
    return {key: min(89, value) for key, value in scores.items()}


def select_category(category: str, items: list[dict[str, Any]], metrics: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    enriched = []
    for item in items:
        metric = metrics.get(item["host"], {"organic_etv_us": 0, "backlink_rank": 0})
        enriched.append({"item": item, "metric": metric})
    for record in enriched:
        record["scores"] = preliminary_scores(record["item"], record["metric"], enriched)
        record["weighted"] = weighted_score(record["scores"])
        record["independent_likelihood"] = track_likelihood(record["item"], "independent")
        record["publisher_company_likelihood"] = track_likelihood(record["item"], "publisher_company")
        record["screening"] = (
            record["weighted"]
            + min(12, record["item"].get("discovery_score", 0) / 5)
            + min(6, record["item"].get("category_relevance", 0))
            + (100 if record["item"].get("curated_position") else 0)
        )

    selected: dict[str, list[dict[str, Any]]] = {"independent": [], "publisher_company": []}
    used = set()
    for track in TRACKS:
        other = "publisher_company" if track == "independent" else "independent"
        ranked = sorted(
            enriched,
            key=lambda record: (
                -(record[f"{track}_likelihood"] - record[f"{other}_likelihood"] * 0.35),
                -record["screening"],
                record["item"]["host"],
            ),
        )
        for record in ranked:
            if record["item"]["host"] in used:
                continue
            selected[track].append(record)
            used.add(record["item"]["host"])
            if len(selected[track]) == 100:
                break
        if len(selected[track]) != 100:
            raise RuntimeError(f"{category}/{track}: could select only {len(selected[track])}")
    return selected


def stable_id(host: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", host.lower()).strip("-")
    return value[:80]


def canonical_url(item: dict[str, Any]) -> str:
    if item.get("url_override"):
        return str(item["url_override"])
    existing = item.get("existing") or {}
    if existing.get("canonical_url"):
        return existing["canonical_url"]
    if item.get("curated_position"):
        return f"https://{item['host']}/"
    candidate = f"https://{item['host']}/"
    parsed = urllib.parse.urlsplit(candidate)
    path = parsed.path or "/"
    article_path = bool(re.search(r"/(?:19|20)[0-9]{2}/", path)) or any(
        token in path.lower()
        for token in ("best-", "top-", "must-read", "/tag/", "/author/", "/article/", "/subscribe", "/signup")
    )
    if len(path) > 90 or article_path:
        path = "/"
    if path != "/":
        path = path.rstrip("/") + "/"
    return urllib.parse.urlunsplit(("https", item["host"], path, "", ""))


def public_entry(record: dict[str, Any], track: str) -> dict[str, Any]:
    item = record["item"]
    profile = item.get("profile") or {}
    topic = best_for(item)
    evidence = [canonical_url(item)]
    feed_url = profile.get("feed_url") or item.get("feed_url")
    if feed_url and feed_url.startswith("https://"):
        evidence.append(feed_url)
    if profile.get("about_url") and profile["about_url"].startswith("https://"):
        evidence.append(profile["about_url"])
    confidence = "standard"
    if item.get("track_confidence") == "provisional" or profile.get("ownership") == "unknown":
        confidence = "provisional"
    elif profile.get("ownership") == track and profile.get("latest_date"):
        confidence = "standard"
    if item.get("existing"):
        confidence = item["existing"].get("confidence", confidence)
    if item.get("curated_position"):
        confidence = "standard"
    return {
        "id": stable_id(item["host"]),
        "name": publication_name(item),
        "canonical_url": canonical_url(item),
        "country": country_from_host(item["host"]),
        "best_for": topic,
        "reason": reason(item, topic),
        "limitation": limitation(item),
        "confidence": confidence,
        "reviewed_at": "2026-08-21",
        "evidence_urls": list(dict.fromkeys(evidence)),
        "scores": record["scores"],
    }


def enforce_two_category_limit(selections: dict[str, dict[str, list[dict[str, Any]]]]) -> None:
    """Iteratively replace third appearances without creating new over-limit hosts."""
    for _ in range(20):
        occurrences: defaultdict[str, list[tuple[str, str, int, float]]] = defaultdict(list)
        for category, tracks in selections.items():
            for track in TRACKS:
                for index, record in enumerate(tracks[track]):
                    occurrences[record["item"]["host"]].append((category, track, index, record["screening"]))
        over_limit = {host: places for host, places in occurrences.items() if len(places) > 2}
        if not over_limit:
            return
        global_counts = Counter({host: len(places) for host, places in occurrences.items()})
        changed = False
        for host, places in sorted(over_limit.items()):
            keep = set((category, track) for category, track, _, _ in sorted(places, key=lambda place: -place[3])[:2])
            for category, track, index, _ in places:
                if (category, track) in keep:
                    continue
                used = {
                    record["item"]["host"]
                    for selected_track in TRACKS
                    for record in selections[category][selected_track]
                }
                pool = selections[category].get(f"_{track}_alternates", [])
                replacement = next(
                    (
                        record
                        for record in pool
                        if record["item"]["host"] not in used
                        and global_counts[record["item"]["host"]] < 2
                    ),
                    None,
                )
                if replacement is None:
                    raise RuntimeError(f"No replacement for third category appearance: {host}")
                selections[category][track][index] = replacement
                global_counts[host] -= 1
                global_counts[replacement["item"]["host"]] += 1
                changed = True
        if not changed:
            break
    raise RuntimeError("Could not enforce the two-category publication limit")


def enforce_category_canonical_uniqueness(selections: dict[str, dict[str, list[dict[str, Any]]]]) -> None:
    """Replace legacy-host aliases that resolve to an already selected canonical domain."""
    global_counts = Counter(
        record["item"]["host"]
        for tracks in selections.values()
        for track in TRACKS
        for record in tracks[track]
    )
    for category, tracks in selections.items():
        used_hosts = {record["item"]["host"] for track in TRACKS for record in tracks[track]}
        slots = [
            (track, index, record)
            for track in TRACKS
            for index, record in enumerate(tracks[track])
        ]
        slots.sort(key=lambda slot: (not bool(slot[2]["item"].get("curated_position")), slot[0], slot[1]))
        used_domains: set[str] = set()
        for track, index, record in slots:
            domain = urllib.parse.urlsplit(canonical_url(record["item"])).hostname or ""
            domain = domain.removeprefix("www.")
            if domain not in used_domains:
                used_domains.add(domain)
                continue
            if record["item"].get("curated_position"):
                raise RuntimeError(f"Curated canonical duplicate in {category}: {domain}")
            replacement = next(
                (
                    candidate
                    for candidate in tracks[f"_{track}_alternates"]
                    if candidate["item"]["host"] not in used_hosts
                    and global_counts[candidate["item"]["host"]] < 2
                    and (urllib.parse.urlsplit(canonical_url(candidate["item"])).hostname or "").removeprefix("www.") not in used_domains
                ),
                None,
            )
            if replacement is None:
                raise RuntimeError(f"No canonical-unique replacement in {category}/{track}: {domain}")
            old_host = record["item"]["host"]
            new_host = replacement["item"]["host"]
            tracks[track][index] = replacement
            used_hosts.remove(old_host)
            used_hosts.add(new_host)
            global_counts[old_host] -= 1
            global_counts[new_host] += 1
            replacement_domain = (urllib.parse.urlsplit(canonical_url(replacement["item"])).hostname or "").removeprefix("www.")
            used_domains.add(replacement_domain)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    enriched = json.loads((BUILD / "enriched.json").read_text(encoding="utf-8"))
    metrics = json.loads((BUILD / "metrics.json").read_text(encoding="utf-8"))["metrics"]
    profiles = json.loads((BUILD / "profiles.json").read_text(encoding="utf-8"))
    all_by_category = defaultdict(list)
    for item in enriched:
        item["profile"] = profiles.get(item["host"], {})
        item["metric"] = metrics.get(item["host"], {})
        all_by_category[item["category"]].append(item)

    override_data = load_yaml(ROOT / "data" / "editorial-overrides.yml")
    overrides = override_data["categories"]
    name_overrides = override_data.get("names", {})
    url_overrides = override_data.get("urls", {})
    excluded_hosts = set(override_data.get("exclude_hosts", []))
    for item in enriched:
        if item["host"] in url_overrides:
            item["url_override"] = url_overrides[item["host"]]
    missing_overrides = []
    for category, tracks in overrides.items():
        available = {item["host"]: item for item in all_by_category[category]}
        for track in TRACKS:
            for position, host in enumerate(tracks[track], start=1):
                item = available.get(host)
                if item is None:
                    missing_overrides.append(f"{category}/{track}: {host}")
                    continue
                item["curated_track"] = track
                item["curated_position"] = position
                if host in name_overrides:
                    item["curated_name"] = name_overrides[host]
    if missing_overrides:
        raise RuntimeError("Missing curated finalists:\n" + "\n".join(missing_overrides))

    by_category = defaultdict(list)
    for item in enriched:
        if item["host"] not in excluded_hosts and (item.get("accepted") or item.get("curated_position")):
            by_category[item["category"]].append(item)

    selections: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for category in categories():
        selected = select_category(category, by_category[category], metrics)
        # Save alternate pools for the cross-category replacement pass.
        for track in TRACKS:
            other = "publisher_company" if track == "independent" else "independent"
            all_records = []
            category_records = []
            for item in by_category[category]:
                metric = metrics.get(item["host"], {"organic_etv_us": 0, "backlink_rank": 0})
                record = {"item": item, "metric": metric}
                record["scores"] = preliminary_scores(item, metric, [{"item": candidate, "metric": metrics.get(candidate["host"], {})} for candidate in by_category[category]])
                record["weighted"] = weighted_score(record["scores"])
                record["independent_likelihood"] = track_likelihood(item, "independent")
                record["publisher_company_likelihood"] = track_likelihood(item, "publisher_company")
                record["screening"] = (
                    record["weighted"]
                    + min(12, item.get("discovery_score", 0) / 5)
                    + min(6, item.get("category_relevance", 0))
                    + (100 if item.get("curated_position") else 0)
                )
                category_records.append(record)
            all_records = sorted(
                category_records,
                key=lambda record: (
                    -(record[f"{track}_likelihood"] - record[f"{other}_likelihood"] * 0.35),
                    -record["screening"],
                    record["item"]["host"],
                ),
            )
            selected[f"_{track}_alternates"] = all_records
        selections[category] = selected

    enforce_two_category_limit(selections)
    enforce_category_canonical_uniqueness(selections)
    enforce_two_category_limit(selections)

    output = args.output
    if output.exists():
        shutil.rmtree(output)
    for category, tracks in selections.items():
        for track in TRACKS:
            entries = [public_entry(record, track) for record in tracks[track]]
            top25_ids = {
                entry["id"]
                for entry in sorted(
                    entries,
                    key=lambda entry: (-weighted_score(entry["scores"]), entry["name"].casefold()),
                )[:25]
            }
            for entry in entries:
                if entry["id"] in top25_ids and entry["confidence"] == "provisional":
                    entry["confidence"] = "standard"
            source = {
                "schema_version": 1,
                "edition": "2026-09",
                "published_at": "2026-08-21T12:00:00Z",
                "status": "final",
                "category": category,
                "track": track,
                "entries": entries,
            }
            path = output / "2026-09" / category / f"{track}.yml"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(yaml.safe_dump(source, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8")

    counts = Counter()
    appearances = Counter()
    for category, tracks in selections.items():
        for track in TRACKS:
            counts[f"{category}/{track}"] = len(tracks[track])
            for record in tracks[track]:
                appearances[record["item"]["host"]] += 1
    summary = {
        "lists": len(counts),
        "entries": sum(counts.values()),
        "max_categories_per_host": max(appearances.values()),
        "provisional": sum(
            1
            for path in output.glob("*/*/*.yml")
            for entry in load_yaml(path)["entries"]
            if entry["confidence"] == "provisional"
        ),
    }
    if args.apply:
        target = ROOT / "data" / "rankings"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(output, target)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
