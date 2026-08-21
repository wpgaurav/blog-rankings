#!/usr/bin/env python3
"""Publish the completed rankings pages after draft-state verification."""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import time
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from deploy_wordpress import load_env, wp_command  # noqa: E402


SITE = "https://gatilab.com"
HUB_SLUG = "blog-rankings"
HUB_TEMPLATE = "templates/blog-rankings-hub.php"
CATEGORY_TEMPLATE = "templates/blog-ranking-category.php"
CATEGORIES = {
    "technology": ("Technology", "Software, devices, AI, security, and the systems shaping technology."),
    "business": ("Business and Entrepreneurship", "Companies, startups, SaaS, leadership, operations, and creator businesses."),
    "marketing-seo": ("Marketing and SEO", "Search, content, copywriting, distribution, analytics, and paid acquisition."),
    "personal-finance": ("Personal Finance", "Saving, investing, debt, tax, planning, and financial independence."),
    "science": ("Science", "Research communication across the physical, life, earth, space, and environmental sciences."),
    "education": ("Education", "Teaching, learning science, higher education, curriculum, and study practice."),
    "health": ("Health and Wellness", "Public health, fitness, nutrition, mental health, and sustainable wellbeing."),
    "travel": ("Travel", "Destination reporting, practical travel guidance, and cultural coverage."),
    "food": ("Food", "Recipes, culinary technique, restaurant culture, food history, and food science."),
    "culture-entertainment": ("Culture and Entertainment", "Books, film, television, music, games, and popular-culture criticism."),
}


def session(env: dict[str, str]) -> requests.Session:
    client = requests.Session()
    client.auth = (env["GL_USERNAME"], env["GL_APPLICATION_PASSWORD"])
    client.headers.update({"Accept": "application/json", "User-Agent": "Gatilab-Blog-Rankings-Publisher/1.0"})
    return client


def page_by_slug(client: requests.Session, slug: str, status: str | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {"slug": slug, "context": "edit", "per_page": 10, "_cb": time.time_ns()}
    if status:
        params["status"] = status
    response = client.get(f"{SITE}/wp-json/wp/v2/pages", params=params, timeout=60)
    response.raise_for_status()
    matches = response.json()
    if len(matches) != 1:
        raise RuntimeError(f"Expected one page for slug {slug}, found {len(matches)}")
    return matches[0]


def media_by_slug(client: requests.Session, slug: str) -> dict[str, Any] | None:
    response = client.get(
        f"{SITE}/wp-json/wp/v2/media",
        params={"slug": slug, "context": "edit", "per_page": 10, "_cb": time.time_ns()},
        timeout=60,
    )
    response.raise_for_status()
    matches = response.json()
    return matches[0] if matches else None


def upload_media(client: requests.Session, path: Path, slug: str, title: str, alt: str) -> dict[str, Any]:
    existing = media_by_slug(client, slug)
    if existing:
        return existing
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    response = client.post(
        f"{SITE}/wp-json/wp/v2/media",
        headers={
            "Content-Disposition": f'attachment; filename="{slug}.png"',
            "Content-Type": mime,
        },
        data=path.read_bytes(),
        timeout=180,
    )
    response.raise_for_status()
    media = response.json()
    update = client.post(
        f"{SITE}/wp-json/wp/v2/media/{media['id']}",
        json={"slug": slug, "title": title, "alt_text": alt, "caption": ""},
        timeout=60,
    )
    update.raise_for_status()
    return update.json()


def set_rank_math(env: dict[str, str], post_id: int, title: str, description: str, keyword: str, image_url: str) -> None:
    values = {
        "rank_math_title": title,
        "rank_math_description": description,
        "rank_math_focus_keyword": keyword,
        "rank_math_facebook_image": image_url,
        "rank_math_twitter_image": image_url,
    }
    for key, value in values.items():
        wp_command(["post", "meta", "update", str(post_id), key, value], env)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publish", action="store_true", help="Publish verified drafts and switch the public hub")
    args = parser.parse_args()
    env = load_env()
    client = session(env)

    index = client.get(f"{SITE}/wp-json/gatilab/v1/blog-rankings", timeout=60)
    index.raise_for_status()
    available = {item["slug"]: item for item in index.json()["categories"]}
    for slug in CATEGORIES:
        item = available.get(slug, {})
        if item.get("edition") != "2026-09" or item.get("status") != "final":
            raise RuntimeError(f"Final payload unavailable for {slug}")

    hub = page_by_slug(client, HUB_SLUG)
    if hub["status"] != "publish":
        raise RuntimeError("Existing rankings hub is no longer published")
    drafts = {slug: page_by_slug(client, slug, "draft") for slug in CATEGORIES}
    for slug, page in drafts.items():
        if page["template"] != CATEGORY_TEMPLATE or page["parent"] != hub["id"]:
            raise RuntimeError(f"Draft identity changed for {slug}")

    backup = {
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hub": hub,
        "drafts": drafts,
    }
    backup_path = ROOT / "build" / "wordpress-release-backup.json"
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path.write_text(json.dumps(backup, indent=2) + "\n", encoding="utf-8")

    hub_media = upload_media(
        client,
        ROOT / "assets" / "social" / "repository-preview.png",
        "gbr-blog-rankings-2026-09",
        "Gatilab Blog Rankings 2026-09",
        "Gatilab Blog Rankings identity with 10 categories, two tracks, and monthly editions.",
    )
    category_media = {}
    for slug, (name, _) in CATEGORIES.items():
        category_media[slug] = upload_media(
            client,
            ROOT / "assets" / "categories" / f"{slug}.png",
            f"gbr-{slug}-2026-09",
            f"{name} Blog Rankings 2026-09",
            f"{name} Blog Rankings with Independent and Publisher and Company tracks.",
        )

    prepared = {}
    for slug, (name, description) in CATEGORIES.items():
        page = drafts[slug]
        response = client.post(
            f"{SITE}/wp-json/wp/v2/pages/{page['id']}",
            json={
                "template": CATEGORY_TEMPLATE,
                "featured_media": category_media[slug]["id"],
                "excerpt": description,
                "status": "draft",
            },
            timeout=90,
        )
        response.raise_for_status()
        title = f"{name} Blog Rankings: Top 100 Blogs by Track"
        meta_description = (
            f"Explore the 2026-09 {name} Blog Rankings: Top 10 Independent and Publisher blogs, "
            "plus complete Top 100 lists and the public methodology."
        )
        set_rank_math(
            env,
            page["id"],
            title,
            meta_description,
            f"{name.lower()} blog rankings",
            category_media[slug]["source_url"],
        )
        prepared[slug] = response.json()

    # Authoritative readback while every new category is still a draft.
    for slug, page in prepared.items():
        verified = page_by_slug(client, slug, "draft")
        if (
            verified["id"] != page["id"]
            or verified["status"] != "draft"
            or verified["template"] != CATEGORY_TEMPLATE
            or verified["featured_media"] != category_media[slug]["id"]
            or verified["parent"] != hub["id"]
        ):
            raise RuntimeError(f"Draft verification failed for {slug}")

    if not args.publish:
        report = {
            "prepared": sorted(prepared),
            "draft_count": len(prepared),
            "media_count": 1 + len(category_media),
            "edition": "2026-09",
            "ready_to_publish": True,
        }
        report_path = ROOT / "build" / "wordpress-preparation.json"
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return

    # Publish category pages. Per publishing policy, do not fetch them again after success.
    published = {}
    for slug, page in prepared.items():
        response = client.post(
            f"{SITE}/wp-json/wp/v2/pages/{page['id']}",
            json={"status": "publish"},
            timeout=90,
        )
        response.raise_for_status()
        result = response.json()
        if result.get("status") != "publish":
            raise RuntimeError(f"Publish failed for {slug}")
        published[slug] = {"status": result["status"], "link": result["link"]}

    # Switch the already-published hub only after all category links are live.
    hub_response = client.post(
        f"{SITE}/wp-json/wp/v2/pages/{hub['id']}",
        json={"template": HUB_TEMPLATE, "featured_media": hub_media["id"]},
        timeout=90,
    )
    hub_response.raise_for_status()
    hub_after = hub_response.json()
    set_rank_math(
        env,
        hub["id"],
        "Gatilab Blog Rankings: Top Blogs by Topic",
        "Explore Gatilab Blog Rankings across 10 topics, with separate Top 100 Independent and Publisher lists, public methodology, nominations, and corrections.",
        "blog rankings",
        hub_media["source_url"],
    )
    hub_verified = page_by_slug(client, HUB_SLUG)
    if hub_verified["template"] != HUB_TEMPLATE or hub_verified["featured_media"] != hub_media["id"]:
        raise RuntimeError("Published hub readback failed")

    wp_command(["cache", "flush"], env)
    try:
        wp_command(["gt-performance", "cache", "purge"], env)
    except RuntimeError:
        pass

    public_hub = requests.get(f"{SITE}/blog-rankings/?nocache={time.time_ns()}", timeout=60)
    public_hub.raise_for_status()
    if (
        "gbr-hub" not in public_hub.text
        or public_hub.text.count('class="gbr-directory__item"') != 10
        or "Blog Rankings by Topic" not in public_hub.text
    ):
        raise RuntimeError("Public hub verification failed")

    report = {
        "published": published,
        "hub": {"status": hub_after["status"], "link": hub_after["link"], "template": hub_verified["template"]},
        "media_count": 1 + len(category_media),
        "source": "main",
        "edition": "2026-09",
    }
    report_path = ROOT / "build" / "wordpress-release.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
