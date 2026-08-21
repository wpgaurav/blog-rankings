#!/usr/bin/env python3
"""Build ranked Markdown and web JSON from reviewed YAML sources."""

from __future__ import annotations

import html
from collections import defaultdict
from pathlib import Path
from typing import Any

from common import (
    ROOT,
    SOURCE_SCHEMA,
    TRACK_LABELS,
    RankingsError,
    canonical_domain,
    categories,
    load_yaml,
    public_entry,
    ranked_entries,
    source_files,
    validate_document,
    write_json,
    write_text,
)


REPOSITORY = "https://github.com/wpgaurav/blog-rankings"


def markdown_for(source: dict[str, Any], category: dict[str, Any], entries: list[dict[str, Any]]) -> str:
    track = source["track"]
    lines = [
        f"# {category['name']}: {TRACK_LABELS[track]}",
        "",
        f"Edition: **{source['edition']}**",
        "",
        f"Status: **{source['status']}**",
        f"Method: [Gatilab Blog Rankings methodology]({REPOSITORY}/blob/main/METHODOLOGY.md)",
        "",
        "> Every ranked destination uses an explicit nofollow link. Beta rankings are provisional.",
        "",
        "| Rank | Publication | Score | Movement | Best For |",
        "|---:|---|---:|---|---|",
    ]
    for entry in entries:
        link = (
            f'<a href="{html.escape(entry["canonical_url"], quote=True)}" '
            f'rel="nofollow noopener">{html.escape(entry["name"])}</a>'
        )
        lines.append(
            f"| {entry['rank']} | {link} | {entry['score']:.1f} | {entry['movement'].title()} | "
            f"{html.escape(entry['best_for'])} |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "Scores compare publications only within this category and track. A rank is not certification of every claim, product, or business associated with a publication.",
            "",
            f"[Nominate a blog or report a correction]({REPOSITORY}/issues/new/choose)",
        ]
    )
    return "\n".join(lines)


def load_sources() -> dict[str, dict[str, tuple[dict[str, Any], list[dict[str, Any]]]]]:
    grouped: dict[str, dict[str, tuple[dict[str, Any], list[dict[str, Any]]]]] = defaultdict(dict)
    known_categories = categories()
    files = source_files()
    if not files:
        raise RankingsError("no ranking source files found")
    for path in files:
        source = load_yaml(path)
        validate_document(source, SOURCE_SCHEMA, str(path.relative_to(ROOT)))
        category_slug = source["category"]
        track = source["track"]
        if category_slug not in known_categories:
            raise RankingsError(f"{path}: unknown category {category_slug}")
        if track in grouped[category_slug]:
            raise RankingsError(f"{path}: duplicate source for {category_slug}/{track}")
        entries = ranked_entries(source["entries"])
        expected = 100 if source["status"] == "final" else 10
        if len(entries) != expected:
            raise RankingsError(
                f"{path}: {source['status']} source requires exactly {expected} entries, found {len(entries)}"
            )
        grouped[category_slug][track] = (source, entries)
    return grouped


def build() -> None:
    known_categories = categories()
    grouped = load_sources()
    index_categories = []
    changes: dict[str, Any] = {}

    for category_slug, tracks in sorted(grouped.items()):
        if set(tracks) != set(TRACK_LABELS):
            raise RankingsError(f"{category_slug}: both tracks are required")

        source_a, entries_a = tracks["independent"]
        source_b, entries_b = tracks["publisher_company"]
        if source_a["edition"] != source_b["edition"] or source_a["status"] != source_b["status"]:
            raise RankingsError(f"{category_slug}: edition and status must match across tracks")

        all_domains = [canonical_domain(item["canonical_url"]) for item in entries_a + entries_b]
        if len(all_domains) != len(set(all_domains)):
            raise RankingsError(f"{category_slug}: a canonical domain appears in both tracks or more than once")

        edition = source_a["edition"]
        published_at = max(source_a["published_at"], source_b["published_at"])
        category = known_categories[category_slug]

        for track, (source, entries) in tracks.items():
            markdown_path = ROOT / "dist" / "markdown" / edition / category_slug / f"{track}.md"
            json_path = ROOT / "dist" / "json" / edition / category_slug / f"{track}.json"
            write_text(markdown_path, markdown_for(source, category, entries))
            write_json(
                json_path,
                {
                    "schema_version": 1,
                    "edition": edition,
                    "status": source["status"],
                    "category": category,
                    "track": {"slug": track, "label": TRACK_LABELS[track]},
                    "count": len(entries),
                    "items": [public_entry(item) for item in entries],
                },
            )

        payload = {
            "schema_version": 1,
            "project": "Gatilab Blog Rankings",
            "edition": edition,
            "status": source_a["status"],
            "generated_at": published_at,
            "category": {
                "slug": category_slug,
                "name": category["name"],
                "description": category["description"],
            },
            "tracks": {
                track: {
                    "slug": track,
                    "label": TRACK_LABELS[track],
                    "count": len(entries),
                    "items": [public_entry(item) for item in entries[:10]],
                }
                for track, (_, entries) in tracks.items()
            },
            "links": {
                "repository": REPOSITORY,
                "methodology": f"{REPOSITORY}/blob/main/METHODOLOGY.md",
                "independent_markdown": f"{REPOSITORY}/blob/main/dist/markdown/{edition}/{category_slug}/independent.md",
                "publisher_company_markdown": f"{REPOSITORY}/blob/main/dist/markdown/{edition}/{category_slug}/publisher_company.md",
            },
        }
        write_json(ROOT / "dist" / "web" / "latest" / f"{category_slug}.json", payload)
        index_categories.append(
            {
                "slug": category_slug,
                "name": category["name"],
                "description": category["description"],
                "edition": edition,
                "status": source_a["status"],
                "endpoint": f"{category_slug}.json",
            }
        )
        changes[category_slug] = {
            track: [{"id": item["id"], "rank": item["rank"], "movement": item["movement"]} for item in entries]
            for track, (_, entries) in tracks.items()
        }

    latest_edition = max(item["edition"] for item in index_categories)
    generated_at = max(
        grouped[item["slug"]]["independent"][0]["published_at"] for item in index_categories
    )
    write_json(
        ROOT / "dist" / "web" / "latest" / "index.json",
        {
            "schema_version": 1,
            "project": "Gatilab Blog Rankings",
            "edition": latest_edition,
            "generated_at": generated_at,
            "categories": index_categories,
        },
    )
    write_json(ROOT / "dist" / "changes" / f"{latest_edition}.json", changes)
    all_final = all(item["status"] == "final" for item in index_categories)
    release_lines = [
        f"# {latest_edition} Edition",
        "",
        (
            "This complete edition contains 100 Independent Blogs and 100 Publisher and Company Blogs in each of 10 categories."
            if all_final
            else "This is a beta platform edition. Every listed entry is provisional until the full Top 100 gate passes."
        ),
        "",
        "Category Winner badges remain unissued until an independent second reviewer completes that governance gate.",
        "",
    ]
    for item in index_categories:
        release_lines.append(f"- [{item['name']}](../dist/markdown/{item['edition']}/{item['slug']}/independent.md)")
    write_text(ROOT / "releases" / f"{latest_edition}.md", "\n".join(release_lines))


if __name__ == "__main__":
    try:
        build()
    except RankingsError as error:
        raise SystemExit(str(error)) from error
