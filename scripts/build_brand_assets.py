"""Rasterize the original Wayline mark; no downloaded runtime assets.

Run: uv run --no-project --with cairosvg==2.8.2 --with pillow==12.1.1 scripts/build_brand_assets.py
On macOS, Cairo may require DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib.
"""

from io import BytesIO
from pathlib import Path

import cairosvg
from PIL import Image

STATIC = Path(__file__).resolve().parents[1] / "lingbot_map/workspace/static"
image = Image.open(
    BytesIO(
        cairosvg.svg2png(
            url=str(STATIC / "icon.svg"),
            output_width=512,
            output_height=512,
            background_color="#11140f",
        )
    )
).convert("RGB")
if len(image.getcolors(512 * 512) or []) < 2:
    raise RuntimeError("Icon rendering was blank")
for name, size in [
    ("icon-512", 512),
    ("icon-192", 192),
    ("apple-touch-icon", 180),
    ("favicon-32", 32),
    ("favicon-16", 16),
]:
    image.resize((size, size), Image.Resampling.LANCZOS).save(STATIC / f"{name}.png", optimize=True)
image.save(STATIC / "favicon.ico", sizes=[(16, 16), (32, 32), (64, 64)])
social = Image.new("RGB", (1200, 630), "#11140f")
social.paste(image.resize((320, 320), Image.Resampling.LANCZOS), (440, 155))
social.save(STATIC / "social-preview.png", optimize=True)
