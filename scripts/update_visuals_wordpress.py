#!/usr/bin/env python3
"""Transactionally replace Blog Rankings media and podium badge URLs."""

from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from deploy_wordpress import load_env, wp_command  # noqa: E402
from publish_wordpress import CATEGORIES, HUB_SLUG, SITE, media_by_slug, page_by_slug, session, upload_media  # noqa: E402


def update_option_json(env: dict[str, str], name: str, value: object) -> None:
    encoded = base64.b64encode(json.dumps(value).encode("utf-8")).decode("ascii")
    code = (
        f"$value=json_decode(base64_decode('{encoded}'),true);"
        f"if(!update_option('{name}',$value,false) && get_option('{name}')!==$value){{throw new Exception('Option update failed');}}"
    )
    wp_command(["eval", code], env)


def option_json(env: dict[str, str], name: str) -> object:
    output = wp_command(["eval", f"echo wp_json_encode(get_option('{name}',array()));"], env)
    return json.loads(output)


def update_social_image(env: dict[str, str], page_id: int, image_url: str) -> None:
    for key in ("rank_math_facebook_image", "rank_math_twitter_image"):
        wp_command(["post", "meta", "update", str(page_id), key, image_url], env)


def attachment_reference_counts(env: dict[str, str], media_ids: list[int]) -> dict[int, int]:
    encoded = base64.b64encode(json.dumps(media_ids).encode("utf-8")).decode("ascii")
    code = (
        f"$ids=json_decode(base64_decode('{encoded}'),true);$out=array();"
        "foreach($ids as $id){$q=new WP_Query(array('post_type'=>'any','post_status'=>'any','meta_key'=>'_thumbnail_id','meta_value'=>(int)$id,'posts_per_page'=>1,'fields'=>'ids'));$out[(int)$id]=(int)$q->found_posts;}"
        "echo wp_json_encode($out);"
    )
    return {int(key): int(value) for key, value in json.loads(wp_command(["eval", code], env)).items()}


def delete_attachments(env: dict[str, str], media_ids: list[int]) -> list[int]:
    if not media_ids:
        return []
    encoded = base64.b64encode(json.dumps(media_ids).encode("utf-8")).decode("ascii")
    code = (
        f"$ids=json_decode(base64_decode('{encoded}'),true);$deleted=array();"
        "foreach($ids as $id){if(wp_delete_attachment((int)$id,true)){$deleted[]=(int)$id;}}"
        "echo wp_json_encode($deleted);"
    )
    return [int(value) for value in json.loads(wp_command(["eval", code], env))]


def main() -> None:
    env = load_env()
    client = session(env)

    hub = page_by_slug(client, HUB_SLUG)
    categories = {slug: page_by_slug(client, slug) for slug in CATEGORIES}
    pages = {HUB_SLUG: hub, **categories}
    for slug, page in pages.items():
        if page.get("status") != "publish":
            raise RuntimeError(f"Expected published page for {slug}")

    old_featured = {slug: int(page.get("featured_media") or 0) for slug, page in pages.items()}
    old_badges = option_json(env, "gatilab_br_rank_badge_urls")
    backup = {
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "featured_media": old_featured,
        "rank_badge_urls": old_badges,
    }
    backup_path = ROOT / "build" / "visual-update-backup.json"
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path.write_text(json.dumps(backup, indent=2) + "\n", encoding="utf-8")

    hub_media = upload_media(
        client,
        ROOT / "assets" / "png-graphics" / "hub.png",
        "gbr-png-hub-2026-09-v2",
        "Gatilab Blog Rankings",
        "Gatilab Blog Rankings award directory with 10 topics, two separate tracks, and complete Top 100 lists.",
    )
    category_media: dict[str, dict[str, Any]] = {}
    for slug, (name, _) in CATEGORIES.items():
        category_media[slug] = upload_media(
            client,
            ROOT / "assets" / "png-graphics" / "categories" / f"{slug}.png",
            f"gbr-png-{slug}-2026-09-v2",
            f"{name} Blog Rankings",
            f"{name} Blog Rankings showing the Top 3 publications in both ranking tracks.",
        )

    badge_media: dict[int, dict[str, Any]] = {}
    badge_labels = {1: "Gold", 2: "Silver", 3: "Bronze"}
    for rank, metal in badge_labels.items():
        badge_media[rank] = upload_media(
            client,
            ROOT / "assets" / "png-graphics" / "rank-badges" / f"rank-{rank}.png",
            f"gbr-rank-{rank}-laurel-v1",
            f"Rank {rank} {metal} Laurel Badge",
            f"{metal} laurel badge for rank {rank}.",
        )

    page_media = {HUB_SLUG: hub_media, **category_media}
    for slug, media in page_media.items():
        page = pages[slug]
        response = client.post(
            f"{SITE}/wp-json/wp/v2/pages/{page['id']}",
            json={"featured_media": media["id"]},
            timeout=90,
        )
        response.raise_for_status()
        update_social_image(env, int(page["id"]), str(media["source_url"]))

    badge_urls = {rank: media["source_url"] for rank, media in badge_media.items()}
    update_option_json(env, "gatilab_br_rank_badge_urls", badge_urls)

    for slug, media in page_media.items():
        verified = page_by_slug(client, slug)
        if int(verified.get("featured_media") or 0) != int(media["id"]):
            raise RuntimeError(f"Featured-media readback failed for {slug}")
    if option_json(env, "gatilab_br_rank_badge_urls") != {str(key): value for key, value in badge_urls.items()}:
        # PHP may preserve numeric keys when encoded as a JSON array.
        verified_badges = option_json(env, "gatilab_br_rank_badge_urls")
        if not isinstance(verified_badges, list) or verified_badges[1:4] != [badge_urls[1], badge_urls[2], badge_urls[3]]:
            raise RuntimeError("Rank badge option readback failed")

    new_ids = {int(media["id"]) for media in page_media.values()}
    obsolete = sorted({value for value in old_featured.values() if value and value not in new_ids})
    reference_counts = attachment_reference_counts(env, obsolete)
    safe_to_delete = [media_id for media_id in obsolete if reference_counts.get(media_id, 0) == 0]
    if len(safe_to_delete) != len(obsolete):
        raise RuntimeError("An old ranking graphic is still referenced and was not deleted")
    deleted = delete_attachments(env, safe_to_delete)
    if sorted(deleted) != safe_to_delete:
        raise RuntimeError("One or more obsolete ranking graphics could not be deleted")

    wp_command(["cache", "flush"], env)
    try:
        wp_command(["gt-performance", "cache", "purge"], env)
    except RuntimeError:
        pass

    report = {
        "updated_pages": sorted(page_media),
        "uploaded_graphics": len(page_media) + len(badge_media),
        "deleted_obsolete_graphics": len(deleted),
        "badge_ranks": sorted(badge_media),
        "verified": True,
    }
    report_path = ROOT / "build" / "visual-update.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
