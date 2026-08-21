#!/usr/bin/env python3
"""Compress generated PNG graphics and record deterministic upload metadata."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = ROOT / "assets" / "png-graphics"


def main() -> None:
    pngquant = shutil.which("pngquant")
    magick = shutil.which("magick")
    if not pngquant or not magick:
        raise RuntimeError("pngquant and ImageMagick are required")

    manifest = {"format": "png", "compression": "pngquant 78-95, stripped", "assets": []}
    for path in sorted(ASSET_ROOT.rglob("*.png")):
        before = path.stat().st_size
        temporary = path.with_name(f".{path.stem}.compressed.png")
        result = subprocess.run(
            [pngquant, "--force", "--quality=78-95", "--speed=1", "--strip", "--output", str(temporary), str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            temporary.unlink(missing_ok=True)
            raise RuntimeError(result.stderr.strip() or f"pngquant failed for {path}")
        temporary.replace(path)

        identify = subprocess.run(
            [magick, "identify", "-format", "%wx%h|%[channels]", str(path)],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        dimensions, channels = identify.split("|", 1)
        if path.parent.name == "rank-badges" and "a" not in channels.lower():
            raise RuntimeError(f"Transparent rank badge lost its alpha channel: {path}")
        manifest["assets"].append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "dimensions": dimensions,
                "channels": channels,
                "original_bytes": before,
                "compressed_bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )

    manifest_path = ASSET_ROOT / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"compressed": len(manifest["assets"]), "manifest": str(manifest_path)}, indent=2))


if __name__ == "__main__":
    main()
