#!/usr/bin/env python3
"""Generate editable, accessible SVG assets for Gatilab Blog Rankings."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import textwrap
from xml.sax.saxutils import escape

import yaml


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets"
PICTURES = Path.home() / "Pictures" / date.today().isoformat() / "gatilab.com" / "blog-rankings"
FONT = "'Google Sans Flex','Google Sans',system-ui,sans-serif"


def svg_document(width: int, height: int, title: str, description: str, body: str, token: str) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="{token}-title {token}-desc">
  <title id="{token}-title">{escape(title)}</title>
  <desc id="{token}-desc">{escape(description)}</desc>
  <defs>
    <pattern id="{token}-dots" width="32" height="32" patternUnits="userSpaceOnUse">
      <circle cx="2" cy="2" r="2" fill="#d8cec5" opacity="0.55"/>
    </pattern>
  </defs>
{body}
</svg>'''


def write_asset(relative: str, content: str) -> None:
    repo_path = OUTPUT / relative
    picture_path = PICTURES / relative
    repo_path.parent.mkdir(parents=True, exist_ok=True)
    picture_path.parent.mkdir(parents=True, exist_ok=True)
    repo_path.write_text(content + "\n", encoding="utf-8")
    picture_path.write_text(content + "\n", encoding="utf-8")
    if relative.startswith("categories/"):
        theme_path = ROOT / "wordpress" / "md-new" / "assets" / "images" / "blog-rankings" / Path(relative).name
        theme_path.parent.mkdir(parents=True, exist_ok=True)
        theme_path.write_text(content + "\n", encoding="utf-8")


def ladder(x: int, y: int, scale: float = 1.0, color: str = "#b94720") -> str:
    bars = [(0, 128, 72), (88, 80, 120), (176, 16, 184)]
    parts = [f'<g id="ranking-ladder" transform="translate({x} {y}) scale({scale})">']
    for offset, top, height in bars:
        parts.append(
            f'<rect x="{offset}" y="{top}" width="64" height="{height}" rx="8" fill="{color}"/>'
        )
        parts.append(
            f'<circle cx="{offset + 32}" cy="{top - 16}" r="7" fill="#2f855a"/>'
        )
    parts.append('<path d="M32 112 L120 64 L208 0" fill="none" stroke="#1f2937" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>')
    parts.append('</g>')
    return "\n".join(parts)


def ranking_mark() -> str:
    body = f'''  <rect width="512" height="512" rx="64" fill="#faf7f2"/>
  <rect x="32" y="32" width="448" height="448" rx="40" fill="url(#gbr-mark-dots)"/>
  {ladder(128, 142, 1.12)}
  <path d="M96 416 H416" stroke="#d8cec5" stroke-width="4"/>
  <text x="96" y="462" font-family="{FONT}" font-size="44" font-weight="700" fill="#1f2937">GATILAB</text>'''
    return svg_document(
        512,
        512,
        "Gatilab Blog Rankings mark",
        "Three ascending coral bars connected by a rising line, representing measured movement through ranked positions.",
        body,
        "gbr-mark",
    )


def repository_preview() -> str:
    body = f'''  <rect width="1280" height="640" fill="#faf7f2"/>
  <rect x="24" y="24" width="1232" height="592" rx="28" fill="url(#gbr-social-dots)" stroke="#d8cec5" stroke-width="2"/>
  <g id="copy">
    <text x="80" y="116" font-family="{FONT}" font-size="38" font-weight="700" fill="#b94720">GATILAB RESEARCH</text>
    <text x="80" y="220" font-family="{FONT}" font-size="76" font-weight="700" fill="#171717">Blog Rankings</text>
    <text x="80" y="294" font-family="{FONT}" font-size="40" font-weight="400" fill="#4b5563">A public, versioned award for useful blogs.</text>
    <path d="M80 352 H656" stroke="#cfc4ba" stroke-width="2"/>
    <text x="80" y="420" font-family="{FONT}" font-size="38" font-weight="600" fill="#1f2937">10 categories</text>
    <text x="330" y="420" font-family="{FONT}" font-size="38" font-weight="600" fill="#1f2937">2 tracks</text>
    <text x="530" y="420" font-family="{FONT}" font-size="38" font-weight="600" fill="#1f2937">Monthly editions</text>
    <text x="80" y="500" font-family="{FONT}" font-size="38" font-weight="400" fill="#6b7280">
      <tspan x="80" dy="0">Public methodology. Versioned source data.</tspan>
      <tspan x="80" dy="52">Open nominations and corrections.</tspan>
    </text>
  </g>
  <g id="visual-field" transform="translate(820 150)">
    <rect x="0" y="0" width="352" height="352" rx="24" fill="#ffffff" stroke="#d8cec5" stroke-width="2"/>
    {ladder(54, 62, 1.15)}
  </g>'''
    return svg_document(
        1280,
        640,
        "Gatilab Blog Rankings",
        "Repository preview showing the measured-momentum ranking ladder and the project's 10 categories, two tracks, and monthly editions.",
        body,
        "gbr-social",
    )


def category_symbol(slug: str, x: int, y: int) -> str:
    symbols = {
        "technology": '<rect x="0" y="0" width="132" height="132" rx="18" fill="none" stroke="#b94720" stroke-width="8"/><path d="M34 66 H98 M66 34 V98 M20 40 H0 M20 92 H0 M112 40 H132 M112 92 H132" stroke="#1f2937" stroke-width="7" stroke-linecap="round"/>',
        "business": '<path d="M8 124 V74 H38 V124 M51 124 V44 H81 V124 M94 124 V14 H124 V124" fill="none" stroke="#b94720" stroke-width="10"/><path d="M6 130 H128" stroke="#1f2937" stroke-width="7"/>',
        "marketing-seo": '<circle cx="66" cy="66" r="56" fill="none" stroke="#1f2937" stroke-width="8"/><circle cx="66" cy="66" r="34" fill="none" stroke="#b94720" stroke-width="8"/><circle cx="66" cy="66" r="11" fill="#2f855a"/><path d="M104 28 L130 2" stroke="#b94720" stroke-width="8"/>',
        "personal-finance": '<path d="M8 112 L42 82 L70 94 L124 32" fill="none" stroke="#b94720" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/><path d="M94 32 H124 V62" fill="none" stroke="#1f2937" stroke-width="8"/><path d="M8 126 H126" stroke="#1f2937" stroke-width="7"/>',
        "science": '<ellipse cx="66" cy="66" rx="60" ry="24" fill="none" stroke="#b94720" stroke-width="7"/><ellipse cx="66" cy="66" rx="60" ry="24" transform="rotate(60 66 66)" fill="none" stroke="#1f2937" stroke-width="7"/><ellipse cx="66" cy="66" rx="60" ry="24" transform="rotate(120 66 66)" fill="none" stroke="#1f2937" stroke-width="7"/><circle cx="66" cy="66" r="9" fill="#2f855a"/>',
        "education": '<path d="M6 24 Q38 14 64 32 V118 Q38 100 6 110 Z M126 24 Q94 14 68 32 V118 Q94 100 126 110 Z" fill="none" stroke="#1f2937" stroke-width="8" stroke-linejoin="round"/><path d="M64 32 V118" stroke="#b94720" stroke-width="7"/>',
        "health": '<path d="M4 72 H34 L48 34 L70 106 L88 58 L100 72 H128" fill="none" stroke="#b94720" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/><path d="M66 128 C24 104 6 78 10 44 C14 12 54 4 66 30 C78 4 118 12 122 44 C126 78 108 104 66 128 Z" fill="none" stroke="#1f2937" stroke-width="7"/>',
        "travel": '<circle cx="66" cy="66" r="58" fill="none" stroke="#1f2937" stroke-width="8"/><path d="M82 50 L98 34 L82 82 L34 98 L50 82 Z" fill="#b94720"/><circle cx="66" cy="66" r="8" fill="#faf7f2"/>',
        "food": '<path d="M10 54 H122 C118 100 96 124 66 124 C36 124 14 100 10 54 Z" fill="none" stroke="#1f2937" stroke-width="8"/><path d="M30 36 C30 16 48 16 48 0 M66 36 C66 16 84 16 84 0 M102 36 C102 16 120 16 120 0" fill="none" stroke="#b94720" stroke-width="7" stroke-linecap="round"/>',
        "culture-entertainment": '<path d="M66 6 L82 44 L124 48 L92 76 L102 118 L66 96 L30 118 L40 76 L8 48 L50 44 Z" fill="none" stroke="#b94720" stroke-width="8" stroke-linejoin="round"/><circle cx="66" cy="66" r="20" fill="none" stroke="#1f2937" stroke-width="7"/>',
    }
    return f'<g id="category-symbol" transform="translate({x} {y})">{symbols[slug]}</g>'


def category_header(category: dict[str, object]) -> str:
    slug = str(category["slug"])
    name = str(category["name"])
    description = str(category["description"])
    name_lines = textwrap.wrap(name, width=20)[:2]
    description_lines = textwrap.wrap(description, width=40)[:4]
    name_tspans = "".join(
        f'<tspan x="96" dy="{0 if index == 0 else 100}">{escape(line)}</tspan>'
        for index, line in enumerate(name_lines)
    )
    description_tspans = "".join(
        f'<tspan x="96" dy="{0 if index == 0 else 64}">{escape(line)}</tspan>'
        for index, line in enumerate(description_lines)
    )
    body = f'''  <rect width="1600" height="900" fill="#faf7f2"/>
  <rect x="32" y="32" width="1536" height="836" rx="30" fill="url(#gbr-{slug}-dots)" stroke="#d8cec5" stroke-width="2"/>
  <g id="category-copy">
    <text x="96" y="132" font-family="{FONT}" font-size="54" font-weight="700" fill="#b94720">GATILAB BLOG RANKINGS</text>
    <text x="96" y="250" font-family="{FONT}" font-size="90" font-weight="700" fill="#171717">{name_tspans}</text>
    <text x="96" y="390" font-family="{FONT}" font-size="52" font-weight="400" fill="#4b5563">{description_tspans}</text>
    <path d="M96 632 H904" stroke="#cfc4ba" stroke-width="3"/>
    <text x="96" y="696" font-family="{FONT}" font-size="48" font-weight="600" fill="#1f2937">Independent Blogs</text>
    <text x="96" y="758" font-family="{FONT}" font-size="48" font-weight="600" fill="#1f2937">Publisher and Company Blogs</text>
    <text x="96" y="834" font-family="{FONT}" font-size="48" font-weight="400" fill="#6b7280">Top 10 on Gatilab. Full Top 100 in GitHub.</text>
  </g>
  <g id="category-visual" transform="translate(1120 180)">
    <rect x="0" y="0" width="352" height="352" rx="26" fill="#ffffff" stroke="#d8cec5" stroke-width="2"/>
    {category_symbol(slug, 110, 70)}
    <path d="M76 260 H276" stroke="#d8cec5" stroke-width="3"/>
    <text x="176" y="326" text-anchor="middle" font-family="{FONT}" font-size="54" font-weight="700" fill="#1f2937">TOP 100</text>
  </g>
  <g id="edition" transform="translate(1120 600)">
    <path d="M0 0 H352" stroke="#1f2937" stroke-width="3"/>
    <text x="0" y="74" font-family="{FONT}" font-size="48" font-weight="600" fill="#b94720">MONTHLY EDITION</text>
    <text x="0" y="132" font-family="{FONT}" font-size="48" font-weight="400" fill="#4b5563"><tspan x="0" dy="0">Public method</tspan><tspan x="0" dy="58">Open corrections</tspan></text>
  </g>'''
    return svg_document(
        1600,
        900,
        f"{name} Blog Rankings",
        f"Gatilab category header for {name}, showing separate Independent and Publisher and Company tracks and a public Top 100.",
        body,
        f"gbr-{slug}",
    )


def methodology_diagram() -> str:
    weights = [("Editorial quality", 30), ("Trust", 20), ("Reach", 20), ("Freshness", 15), ("UX", 10), ("Impact", 5)]
    parts = ['  <rect width="1600" height="900" fill="#faf7f2"/>', '  <rect x="32" y="32" width="1536" height="836" rx="30" fill="url(#gbr-method-dots)" stroke="#d8cec5" stroke-width="2"/>']
    parts.append(f'  <text x="88" y="128" font-family="{FONT}" font-size="54" font-weight="700" fill="#b94720">HOW THE SCORE IS BUILT</text>')
    parts.append(f'  <text x="88" y="214" font-family="{FONT}" font-size="82" font-weight="700" fill="#171717"><tspan x="88" dy="0">100 points.</tspan><tspan x="88" dy="88">6 visible components.</tspan></text>')
    x = 88
    y = 336
    colors = ["#b94720", "#1f2937", "#374151", "#6b7280", "#2f855a", "#2563eb"]
    for index, (label, value) in enumerate(weights):
        width = value * 13
        parts.append(f'  <g id="weight-{index}">')
        parts.append(f'    <text x="{x}" y="{y + 46}" font-family="{FONT}" font-size="48" font-weight="600" fill="#1f2937">{label}</text>')
        parts.append(f'    <rect x="{x + 370}" y="{y}" width="{width}" height="64" rx="8" fill="{colors[index]}"/>')
        parts.append(f'    <text x="{x + 390 + width}" y="{y + 46}" font-family="{FONT}" font-size="48" font-weight="700" fill="#1f2937">{value}%</text>')
        parts.append('  </g>')
        y += 72
    parts.append(f'  <text x="88" y="786" font-family="{FONT}" font-size="48" font-weight="400" fill="#4b5563"><tspan x="88" dy="0">Public signals monitor candidates.</tspan><tspan x="88" dy="54">Human review sets the final order.</tspan></text>')
    return svg_document(1600, 900, "Gatilab Blog Rankings scoring method", "Six weighted components total 100 points, led by editorial quality at 30 percent.", "\n".join(parts), "gbr-method")


def monthly_flow() -> str:
    steps = ["Nominations", "Data checks", "Editorial review", "Draft PR", "Tagged edition", "Gatilab refresh"]
    parts = ['  <rect width="1600" height="900" fill="#0f0f0f"/>']
    parts.append(f'  <text x="88" y="126" font-family="{FONT}" font-size="54" font-weight="700" fill="#e8836f">MONTHLY RELEASE FLOW</text>')
    parts.append(f'  <text x="88" y="220" font-family="{FONT}" font-size="76" font-weight="700" fill="#fafafa"><tspan x="88" dy="0">Automation prepares.</tspan><tspan x="88" dy="88">A human publishes.</tspan></text>')
    y = 420
    for index, step in enumerate(steps, start=1):
        x = 88 + ((index - 1) % 3) * 490
        row = (index - 1) // 3
        yy = y + row * 200
        parts.append(f'  <g id="flow-{index}">')
        parts.append(f'    <circle cx="{x + 42}" cy="{yy + 42}" r="40" fill="#b94720"/>')
        parts.append(f'    <text x="{x + 42}" y="{yy + 57}" text-anchor="middle" font-family="{FONT}" font-size="48" font-weight="700" fill="#ffffff">{index}</text>')
        parts.append(f'    <text x="{x + 104}" y="{yy + 56}" font-family="{FONT}" font-size="48" font-weight="600" fill="#f4f4f5">{step}</text>')
        parts.append('  </g>')
    parts.append(f'  <text x="88" y="842" font-family="{FONT}" font-size="48" font-weight="400" fill="#a1a1aa">Invalid data never replaces the last-known-good edition.</text>')
    return svg_document(1600, 900, "Gatilab Blog Rankings monthly release flow", "Six steps move nominations through automated checks, editorial review, a draft pull request, a tagged edition, and the Gatilab refresh.", "\n".join(parts), "gbr-flow")


def badge_template(label: str, filename: str) -> None:
    body = f'''  <rect width="800" height="800" rx="96" fill="#0f0f0f"/>
  <rect x="48" y="48" width="704" height="704" rx="64" fill="none" stroke="#3f3f46" stroke-width="4"/>
  {ladder(260, 130, 1.15, '#e8836f')}
  <text x="400" y="500" text-anchor="middle" font-family="{FONT}" font-size="72" font-weight="700" fill="#fafafa">{escape(label)}</text>
  <text x="400" y="588" text-anchor="middle" font-family="{FONT}" font-size="52" font-weight="600" fill="#e8836f">BADGE TEMPLATE</text>
  <text x="400" y="670" text-anchor="middle" font-family="{FONT}" font-size="42" font-weight="400" fill="#a1a1aa">NOT AN ISSUED AWARD</text>'''
    write_asset(
        f"badges/templates/{filename}.svg",
        svg_document(800, 800, f"{label} badge template", "An unissued Gatilab Blog Rankings badge template, clearly marked as not an award.", body, f"gbr-badge-{filename}"),
    )


def issued_badge(category: dict[str, object], track: str, level: str, edition: str) -> str:
    category_name = str(category["name"])
    category_lines = textwrap.wrap(category_name, width=18)[:2]
    category_tspans = "".join(
        f'<tspan x="400" dy="{0 if index == 0 else 72}">{escape(line)}</tspan>'
        for index, line in enumerate(category_lines)
    )
    if track == "independent":
        track_label = "INDEPENDENT"
        track_tspans = '<tspan x="400" dy="0">INDEPENDENT</tspan>'
    else:
        track_label = "PUBLISHER + COMPANY"
        track_tspans = '<tspan x="400" dy="0">PUBLISHER +</tspan><tspan x="400" dy="72">COMPANY</tspan>'
    body = f'''  <rect width="800" height="800" rx="96" fill="#0f0f0f"/>
  <rect x="48" y="48" width="704" height="704" rx="64" fill="none" stroke="#3f3f46" stroke-width="4"/>
  {ladder(280, 68, 1, '#e8836f')}
  <text x="400" y="340" text-anchor="middle" font-family="{FONT}" font-size="96" font-weight="700" fill="#fafafa">{escape(level)}</text>
  <text x="400" y="420" text-anchor="middle" font-family="{FONT}" font-size="70" font-weight="600" fill="#e8836f">{track_tspans}</text>
  <text x="400" y="570" text-anchor="middle" font-family="{FONT}" font-size="70" font-weight="700" fill="#fafafa">{category_tspans}</text>
  <text x="400" y="742" text-anchor="middle" font-family="{FONT}" font-size="70" font-weight="600" fill="#a1a1aa">{escape(edition)} EDITION</text>'''
    return svg_document(
        800,
        800,
        f"{category_name} {track_label.title()} {level} badge",
        f"Issued Gatilab Blog Rankings {level} badge for the {category_name} {track_label.lower()} track in the {edition} edition.",
        body,
        f"gbr-issued-{category['slug']}-{track}-{level.lower().replace(' ', '-')}",
    )


def main() -> None:
    category_data = yaml.safe_load((ROOT / "categories.yml").read_text(encoding="utf-8"))["categories"]
    write_asset("identity/ranking-mark.svg", ranking_mark())
    write_asset("social/repository-preview.svg", repository_preview())
    write_asset("diagrams/methodology.svg", methodology_diagram())
    write_asset("diagrams/monthly-flow.svg", monthly_flow())
    for category in category_data:
        write_asset(f"categories/{category['slug']}.svg", category_header(category))
    badge_template("CATEGORY WINNER", "category-winner")
    badge_template("TOP 10", "top-10")
    badge_template("TOP 100", "top-100")
    edition = "2026-09"
    badge_index = []
    for category in category_data:
        for track in ("independent", "publisher_company"):
            source_path = ROOT / "data" / "rankings" / edition / str(category["slug"]) / f"{track}.yml"
            source = yaml.safe_load(source_path.read_text(encoding="utf-8"))
            if source.get("status") != "final" or len(source.get("entries", [])) != 100:
                raise RuntimeError(f"Cannot issue badges from incomplete source: {source_path}")
            for level, slug in (("TOP 10", "top-10"), ("TOP 100", "top-100")):
                relative = f"badges/{edition}/{category['slug']}/{track}-{slug}.svg"
                write_asset(relative, issued_badge(category, track, level, edition))
                badge_index.append(
                    {
                        "edition": edition,
                        "category": category["slug"],
                        "track": track,
                        "level": level,
                        "asset": relative,
                    }
                )
    (OUTPUT / "badges" / edition / "index.json").write_text(json.dumps(badge_index, indent=2) + "\n", encoding="utf-8")
    print(f"Generated SVG assets in {OUTPUT} and {PICTURES}")


if __name__ == "__main__":
    main()
