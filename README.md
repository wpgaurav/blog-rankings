# Gatilab Blog Rankings

[![Buy me a coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-FFDD00?style=flat&logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/gauravtiwari)

Gatilab Blog Rankings is a transparent, versioned award and research project for notable blogs worldwide.

Each category has two separate tracks:

- Independent Blogs
- Publisher and Company Blogs

Gatilab presents the Top 10 on the web. This repository publishes the complete Top 100, methodology, source records, monthly movement, and generated API payloads.

## Current Status

The 2026-09 release candidate contains 10 categories, 2 separate tracks per category, and 100 ranked publications in every track. Top 10 and Top 100 badges are generated from the final data. Category Winner badges remain unissued until an independent second reviewer completes that governance gate.

## How It Works

1. Public signals help discover candidates and identify material changes.
2. Human reviewers score eligible finalists with the published rubric.
3. Validation checks the schema, ranks, links, counts, and relationship attributes.
4. A reviewed monthly pull request creates an immutable edition.
5. Gatilab reads generated JSON and keeps a last-known-good copy.

Read [METHODOLOGY.md](METHODOLOGY.md) before interpreting a rank or submitting a nomination.

## Repository Map

```text
data/                  Human-edited ranking sources
dist/                  Generated Markdown and JSON
schema/                Machine-readable contracts
scripts/               Build, validation, rendering, compression, and publishing tools
assets/                SVG masters plus compressed production PNG graphics
graphics/png/source/   Tailwind HTML sources for hub, category, and rank graphics
wordpress/md-new/      Gatilab child-theme integration
.github/               Validation, release, nomination, correction, and appeal flows
```

## Local Build

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/build.py
.venv/bin/python scripts/validate.py
.venv/bin/python -m unittest discover -s tests
```

Generated files in `dist/` are committed, but must not be edited by hand.

## PNG Graphics

The production graphic family follows the Gatilab Everyday Evidence system: a neutral structured grid, one restrained red accent, familiar award/reference-sheet frames, and real ranking relationships. The hub and category graphics render at 1600×900. The gold, silver, and bronze rank laurels render at 512×512 with transparent outer pixels.

The HTML sources use Tailwind CSS v4 and the Gatilab display/body font roles. Regenerate them after the reviewed ranking data changes, then compress the PNGs before uploading them to WordPress:

```bash
python3 scripts/build_png_graphics.py
npm install
npx playwright install chromium
npm run render:graphics
python3 scripts/compress_png_graphics.py
```

The compression manifest records dimensions, color channels, byte sizes, and SHA-256 hashes. Keep the transparent rank badges in the WordPress media library; the child theme reads their URLs from `gatilab_br_rank_badge_urls` and reads the hub/category art from each page's featured image.

## Public URLs

- Rankings hub: <https://gatilab.com/blog-rankings/>
- Methodology: <https://github.com/wpgaurav/blog-rankings/blob/main/METHODOLOGY.md>
- Nominations and corrections: <https://github.com/wpgaurav/blog-rankings/issues/new/choose>

## Independence

Ranking positions are not sold, reserved, exchanged, or promised. Sponsorship may support the project only when it is clearly separated from the ranking system.

## Support This Project

The complete Top 100 for every Gatilab Blog Rankings track is in this repo and free to reuse under CC BY 4.0, along with the methodology, source records and monthly movement. Human reviewers score eligible finalists against the published rubric and every monthly edition goes through schema and link validation plus a reviewed pull request.

If the full Top 100 lists helped you find blogs worth reading in a category you follow, you can buy me a coffee and it won't change where any blog ranks.

<a href="https://buymeacoffee.com/gauravtiwari"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy me a coffee" height="50"></a>

Starring the repo helps, and if you spot a wrong link or a blog that belongs in one of the categories, you can send a correction or a nomination through the issue forms.

## License

Code is licensed under GPL-2.0-or-later. Public ranking data and original documentation are licensed under CC BY 4.0. See [LICENSE-DATA.md](LICENSE-DATA.md).
Transparent global blog rankings by Gatilab, with public methodology, data, monthly editions, and WordPress integration.
