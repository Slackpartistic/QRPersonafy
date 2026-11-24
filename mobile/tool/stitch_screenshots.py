"""Joins tool/screenshots/*.png side by side into docs/images/phone.png. Needs Pillow."""

from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent
shots = [Image.open(path).convert("RGB") for path in sorted((HERE / "screenshots").glob("*.png"))]
gap = 8
out = Image.new("RGB", (sum(s.width for s in shots) + gap * (len(shots) - 1), shots[0].height), (232, 234, 240))
x = 0
for shot in shots:
    out.paste(shot, (x, 0))
    x += shot.width + gap
out.save(HERE.parent.parent / "docs" / "images" / "phone.png", optimize=True)
