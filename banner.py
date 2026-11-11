#!/usr/bin/env python3
"""banner.py — the share card (og.png) and the home-screen icon (touch-icon.png).

both are cut from the night painting in art/, so repaint first if the picture
changed:  python3 _tools/paint/bench.py && python3 banner.py
needs pillow. the lettering is alegreya, the site's reading face."""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
W, H = 1200, 630
GROUND, INK = (16, 20, 42), (240, 231, 211)

src = Image.open(os.path.join(ROOT, "art", "bench-night-wide.webp")).convert("RGB")

# the card: the painting, with the ground it was painted on brought back up
# across the bottom for the words to sit on
k = W / src.width
pic = src.resize((W, round(src.height * k)), Image.LANCZOS)          # 1200 x 600
card = Image.new("RGB", (W, H), GROUND)
card.paste(pic, (0, -34))
veil = Image.new("L", (W, H), 0)
vd = ImageDraw.Draw(veil)
for y in range(H):
    t = min(1.0, max(0.0, (y - 330) / 170))
    vd.line([(0, y), (W, y)], fill=int(255 * (t * t * (3 - 2 * t)) * 0.93))
card = Image.composite(Image.new("RGB", (W, H), GROUND), card, veil)
d = ImageDraw.Draw(card)


def face(name, size, weight=None):
    f = ImageFont.truetype(os.path.join(ROOT, "fonts", name), size)
    if weight:
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
    return f


d.text((64, 446), "dead silicon", font=face("Alegreya-Italic.woff2", 92, 800), fill=INK)
d.text((66, 556), "a from-scratch llm inference engine, built on a gtx 1050 and 16gb of ram.",
       font=face("Alegreya.woff2", 30, 500), fill=(240, 231, 211))
# 256 colours, dithered: a third of the weight, and paint hides the dither
card.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG).save(
    os.path.join(ROOT, "og.png"), optimize=True)

# the icon: the bulb
bx, by = int(0.3841 * src.width), int(0.2107 * src.height)
r = 150
icon = src.crop((bx - r, by - r + 20, bx + r, by + r + 20)).resize((180, 180), Image.LANCZOS)
icon.save(os.path.join(ROOT, "touch-icon.png"), optimize=True)

# and the same bulb, tiny, for browsers that ask for /favicon.ico whatever the page says
icon.save(os.path.join(ROOT, "favicon.ico"), sizes=[(32, 32), (16, 16)])

for n in ("og.png", "touch-icon.png", "favicon.ico"):
    print(f"{n}  {os.path.getsize(os.path.join(ROOT, n)) / 1024:.0f} kb")
