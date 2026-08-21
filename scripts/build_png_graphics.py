#!/usr/bin/env python3
"""Build Tailwind HTML sources for the Gatilab Blog Rankings PNG family."""

from __future__ import annotations

from datetime import date
from html import escape
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "graphics" / "png" / "source"
PICTURES = Path.home() / "Pictures" / date.today().isoformat() / "gatilab.com" / "blog-rankings" / "source"

FONT_FACES = """
@font-face { font-family:'Valley Sans'; src:url('file:///Library/Fonts/ValleySans%5Bwght%5D.ttf') format('truetype'); font-weight:100 900; font-style:normal; font-display:block; }
@font-face { font-family:'Really Sans Large'; src:url('file:///Users/gauravtiwari/Library/Fonts/ReallySansLarge-Regular.otf') format('opentype'); font-weight:400; font-style:normal; }
@font-face { font-family:'Really Sans Large'; src:url('file:///Users/gauravtiwari/Library/Fonts/ReallySansLarge-Semibold.otf') format('opentype'); font-weight:600; font-style:normal; }
@font-face { font-family:'Really Sans Large'; src:url('file:///Users/gauravtiwari/Library/Fonts/ReallySansLarge-Bold.otf') format('opentype'); font-weight:700; font-style:normal; }
"""

BASE_CSS = """
:root { --accent:#dc2626; --ink:#0a0a0a; --soft:#52525b; --faint:#71717a; --wash:#f4f5f7; --surface:#ffffff; --line:#d9dce2; }
* { box-sizing:border-box; }
html, body { margin:0; min-height:100%; }
html { font-family:'Valley Sans',sans-serif; letter-spacing:0; }
h1, h2, h3, .heading { font-family:'Really Sans Large',sans-serif; letter-spacing:0!important; }
.canvas-grid { background-color:var(--wash); background-image:linear-gradient(var(--line) 1px,transparent 1px),linear-gradient(90deg,var(--line) 1px,transparent 1px); background-size:24px 24px; }
.safe { padding:28px 32px; }
.eyebrow { color:var(--accent); font-size:12px; font-weight:750; line-height:1; text-transform:uppercase; }
.muted { color:var(--soft); }
.tabular { font-variant-numeric:tabular-nums; }
"""


def document(title: str, body: str, extra_css: str = "", transparent: bool = False) -> str:
    background = "transparent" if transparent else "var(--wash)"
    return f"""<!doctype html>
<html lang="en" class="antialiased">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=1080">
<title>{escape(title)}</title>
<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
<style>
{FONT_FACES}
{BASE_CSS}
body {{ background:{background}; }}
{extra_css}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def write_source(filename: str, content: str) -> None:
    for base in (SOURCE, PICTURES):
        base.mkdir(parents=True, exist_ok=True)
        (base / filename).write_text(content, encoding="utf-8")


def ranking_rows(items: list[dict[str, object]]) -> str:
    rows = []
    for item in items[:3]:
        rows.append(
            f"""<li class="grid grid-cols-[30px_minmax(0,1fr)] items-center border-t border-[#e3e4e8] py-[10px]">
  <span class="tabular text-[15px] font-[780] text-[#0a0a0a]">{int(item['rank']):02d}</span>
  <span class="truncate text-[15px] font-[650] text-[#0a0a0a]">{escape(str(item['name']))}</span>
</li>"""
        )
    return "\n".join(rows)


def category_graphic(payload: dict[str, object]) -> str:
    category = payload["category"]
    independent = payload["tracks"]["independent"]["items"]
    publisher = payload["tracks"]["publisher_company"]["items"]
    name = str(category["name"])
    title_size = "text-[46px]" if len(name) < 22 else "text-[38px]"
    body = f"""<main class="canvas-grid relative isolate h-[450px] w-[800px] overflow-hidden safe" data-min-font-size="11" data-min-text-padding="8">
  <div class="absolute left-0 top-0 h-full w-[6px] bg-[#dc2626]" aria-hidden="true"></div>
  <header class="relative z-10 flex items-end justify-between gap-8">
    <div class="min-w-0">
      <p class="eyebrow mb-[13px]">Gatilab Blog Rankings</p>
      <h1 class="heading {title_size} max-w-[620px] font-[700] leading-[0.98] text-[#0a0a0a]">{escape(name)} Blog Rankings</h1>
    </div>
    <p class="shrink-0 pb-[4px] text-right text-[12px] font-[650] leading-[1.35] text-[#52525b]">2 tracks<br>1 public record</p>
  </header>

  <section class="relative z-10 mt-[22px] grid grid-cols-2 overflow-hidden border border-[#d2d4da] bg-white" aria-label="Top three publications in both ranking tracks">
    <div class="p-[18px_22px_15px]">
      <p class="mb-[10px] text-[12px] font-[780] uppercase text-[#52525b]">Independent Blogs</p>
      <ol class="m-0 list-none p-0">{ranking_rows(independent)}</ol>
    </div>
    <div class="border-l border-[#d2d4da] p-[18px_22px_15px]">
      <p class="mb-[10px] text-[12px] font-[780] uppercase text-[#52525b]">Publisher + Company</p>
      <ol class="m-0 list-none p-0">{ranking_rows(publisher)}</ol>
    </div>
    <div class="col-span-2 flex items-center justify-between bg-[#0a0a0a] px-[22px] py-[12px] text-white">
      <p class="text-[12px] font-[680]">Top 10 on Gatilab</p>
      <span class="h-px w-[104px] bg-[#3f3f46]" aria-hidden="true"></span>
      <p class="text-[12px] font-[680]">Complete Top 100 in GitHub</p>
    </div>
  </section>

  <footer class="absolute inset-x-[32px] bottom-[17px] z-10 flex items-center justify-between text-[11px] font-[620] text-[#52525b]">
    <span>Editorial quality leads the score</span>
    <span>Open nominations and corrections</span>
  </footer>
</main>"""
    return document(f"{name} Blog Rankings", body)


def hub_graphic(index: dict[str, object]) -> str:
    categories = [item["name"] for item in index["categories"]]
    topic_rows = "".join(
        f'<li class="border-t border-[#e3e4e8] py-[4px] text-[12px] font-[650] text-[#0a0a0a]">{escape(str(name))}</li>'
        for name in categories
    )
    body = f"""<main class="canvas-grid relative isolate h-[450px] w-[800px] overflow-hidden safe" data-min-font-size="11" data-min-text-padding="8">
  <div class="absolute left-0 top-0 h-full w-[6px] bg-[#dc2626]" aria-hidden="true"></div>
  <header class="relative z-10 flex items-end justify-between gap-8">
    <div>
      <p class="eyebrow mb-[13px]">Gatilab Research</p>
      <h1 class="heading text-[54px] font-[700] leading-[0.94] text-[#0a0a0a]">Blog Rankings</h1>
      <p class="mt-[12px] text-[16px] font-[540] text-[#52525b]">A public, versioned award for useful blogs.</p>
    </div>
    <div class="grid shrink-0 grid-cols-3 border-y border-[#aeb2ba] text-center">
      <div class="px-[14px] py-[7px]"><strong class="heading block text-[24px] leading-none">10</strong><span class="text-[11px] font-[650] text-[#52525b]">topics</span></div>
      <div class="border-x border-[#aeb2ba] px-[14px] py-[7px]"><strong class="heading block text-[24px] leading-none">2</strong><span class="text-[11px] font-[650] text-[#52525b]">tracks</span></div>
      <div class="px-[14px] py-[7px]"><strong class="heading block text-[24px] leading-none">100</strong><span class="text-[11px] font-[650] text-[#52525b]">per track</span></div>
    </div>
  </header>

  <section class="relative z-10 mt-[18px] grid h-[224px] grid-cols-[1.25fr_.75fr] grid-rows-[180px_44px] overflow-hidden border border-[#d2d4da] bg-white" aria-label="Award index and publication model">
    <div class="p-[13px_22px_9px]">
      <p class="mb-[5px] text-[12px] font-[780] uppercase text-[#52525b]">Award Directory</p>
      <ul class="grid list-none grid-cols-2 gap-x-[24px] p-0">{topic_rows}</ul>
    </div>
    <div class="border-l border-[#d2d4da] p-[12px_20px]">
      <p class="mb-[7px] text-[12px] font-[780] uppercase text-[#52525b]">Separate Tracks</p>
      <div class="border-y border-[#e3e4e8] py-[7px]">
        <p class="text-[15px] font-[700] text-[#0a0a0a]">Independent Blogs</p>
        <p class="mt-[3px] text-[11px] leading-[1.35] text-[#52525b]">Creator-led and independently owned publications</p>
      </div>
      <div class="border-b border-[#e3e4e8] py-[7px]">
        <p class="text-[15px] font-[700] text-[#0a0a0a]">Publisher + Company</p>
        <p class="mt-[3px] text-[11px] leading-[1.35] text-[#52525b]">Newsrooms, institutions, and company publications</p>
      </div>
    </div>
    <div class="col-span-2 flex items-center justify-between bg-[#0a0a0a] px-[22px] text-white">
      <p class="text-[12px] font-[680]">Top 10 on Gatilab</p>
      <span class="h-px w-[104px] bg-[#3f3f46]" aria-hidden="true"></span>
      <p class="text-[12px] font-[680]">Complete Top 100 in GitHub</p>
    </div>
  </section>

  <footer class="absolute inset-x-[32px] bottom-[17px] z-10 flex items-center justify-between text-[11px] font-[620] text-[#52525b]">
    <span>Public methodology</span>
    <span>Human-reviewed monthly releases</span>
  </footer>
</main>"""
    return document("Gatilab Blog Rankings", body)


BADGE_COLORS = {
    1: ("#7c5700", "#d4af37", "#fff0a6", "#8c6500", "#2d2100"),
    2: ("#68707a", "#bfc5ce", "#f5f7fa", "#7f8791", "#20252b"),
    3: ("#713910", "#b87333", "#efb17d", "#7e421a", "#fffaf5"),
}


def badge_graphic(rank: int) -> str:
    edge, metal, shine, shade, number = BADGE_COLORS[rank]
    leaves = []
    transforms = [(-63, -46, -62), (-76, -18, -42), (-79, 14, -24), (-70, 45, -6), (-53, 72, 12), (-61, 92, 28)]
    for side in (-1, 1):
        for index, (x, y, rotation) in enumerate(transforms):
            left = 128 + side * abs(x)
            angle = rotation if side < 0 else -rotation
            leaves.append(
                f'<span class="leaf" style="left:{left}px;top:{128 + y}px;transform:translate(-50%,-50%) rotate({angle}deg) scaleX({side});"></span>'
            )
    extra_css = f"""
.badge {{ --edge:{edge}; --metal:{metal}; --shine:{shine}; --shade:{shade}; position:relative; width:256px; height:256px; background:transparent; }}
.laurel {{ position:absolute; inset:0; }}
.leaf {{ position:absolute; width:23px; height:45px; border:1px solid var(--edge); border-radius:100% 0 100% 0; background:linear-gradient(135deg,var(--shine) 0%,var(--metal) 48%,var(--shade) 100%); box-shadow:inset 2px 2px 4px rgba(255,255,255,.42),inset -2px -2px 4px rgba(0,0,0,.18); }}
.stem-left,.stem-right {{ position:absolute; top:74px; width:2px; height:124px; border-radius:99px; background:linear-gradient(var(--shine),var(--shade)); transform-origin:50% 100%; }}
.stem-left {{ left:66px; transform:rotate(-24deg); }}
.stem-right {{ right:66px; transform:rotate(24deg); }}
.medallion {{ position:absolute; left:50%; top:50%; width:118px; height:118px; transform:translate(-50%,-50%); border:3px solid var(--edge); border-radius:999px; background:radial-gradient(circle at 34% 27%,var(--shine) 0 16%,var(--metal) 42%,var(--shade) 100%); box-shadow:0 7px 16px rgba(10,10,10,.22),inset 0 0 0 5px color-mix(in srgb,var(--shine) 56%,transparent),inset 0 0 0 8px color-mix(in srgb,var(--edge) 72%,transparent); }}
.number {{ color:{number}; font-family:'Really Sans Large',sans-serif; font-size:72px; font-weight:700; line-height:1; text-shadow:0 1px 0 rgba(255,255,255,.28); }}
"""
    body = f"""<main class="badge relative h-[256px] w-[256px] overflow-hidden" data-min-font-size="11" data-min-text-padding="8" aria-label="Rank {rank} laurel badge">
  <div class="laurel" aria-hidden="true">
    <span class="stem-left"></span><span class="stem-right"></span>{''.join(leaves)}
  </div>
  <div class="medallion flex items-center justify-center"><span class="number tabular">{rank}</span></div>
</main>"""
    return document(f"Rank {rank} laurel badge", body, extra_css=extra_css, transparent=True)


def main() -> None:
    index = json.loads((ROOT / "dist" / "web" / "latest" / "index.json").read_text(encoding="utf-8"))
    write_source("hub.html", hub_graphic(index))
    for item in index["categories"]:
        slug = item["slug"]
        payload = json.loads((ROOT / "dist" / "web" / "latest" / f"{slug}.json").read_text(encoding="utf-8"))
        write_source(f"category-{slug}.html", category_graphic(payload))
    for rank in (1, 2, 3):
        write_source(f"rank-{rank}.html", badge_graphic(rank))
    print(f"Wrote 14 PNG source files to {SOURCE}")


if __name__ == "__main__":
    main()
