"""dead-silicon og:image — drawn by the same seeded sampler as the site's orb.
Ports mulberry32(7) and the ring geometry from drawOrb() in index.html, so the
banner is literally the same object the footer draws, at 12x scale."""
from PIL import Image, ImageDraw, ImageFont
import math

W, H = 1200, 630
CREAM, INK, EMBER, LINE = (232,230,223), (23,24,27), (150,70,20), (23,24,27,40)

def mulberry32(seed):
    t = seed & 0xFFFFFFFF
    def imul(a,b):
        r = (a*b) & 0xFFFFFFFF
        return r-0x100000000 if r >= 0x80000000 else r
    def nxt():
        nonlocal t
        t = (t + 0x6D2B79F5) & 0xFFFFFFFF
        r = imul(t ^ (t >> 15), 1 | t) & 0xFFFFFFFF
        r = ((r + imul(r ^ (r >> 7), 61 | r)) & 0xFFFFFFFF) ^ r
        return ((r ^ (r >> 14)) & 0xFFFFFFFF) / 4294967296
    return nxt

img = Image.new("RGB", (W, H), CREAM)
d = ImageDraw.Draw(img, "RGBA")

# corner ticks — the same frame furniture as the site and the timelapses
T, M, w = 46, 54, 2
for (x,y,dx,dy) in [(M,M,1,1),(W-M,M,-1,1),(M,H-M,1,-1),(W-M,H-M,-1,-1)]:
    d.rectangle([min(x,x+dx*T), y-w//2, max(x,x+dx*T), y+w//2], fill=INK)
    d.rectangle([x-w//2, min(y,y+dy*T), x+w//2, max(y,y+dy*T)], fill=INK)

# the orb, seed 7, identical rings to drawOrb()
rnd = mulberry32(7)
pts = [(0,0,2.2)]
for R, cnt in [(8,6),(14,10),(20,14),(25,16)]:
    for j in range(cnt):
        a = 6.28318*j/cnt + R*0.35
        dx, dy = R*math.cos(a), R*math.sin(a)
        shade = max(0.0, (dx+dy)/(1.414*R))
        pts.append((dx, dy, 0.9 + 1.4*shade + (rnd()*0.3 - 0.15)))

k, ox, oy = 5.6, 232, H//2
for i,(px,py,r) in enumerate(pts):
    col = EMBER if i % 9 == 4 else INK
    rr = max(2.0, r*k)
    d.ellipse([ox+px*k-rr, oy+py*k-rr, ox+px*k+rr, oy+py*k+rr], fill=col)

F = "/home/claude/ttf/JetBrainsMono-%s.ttf"
bold = ImageFont.truetype(F % "ExtraBold", 76)
reg  = ImageFont.truetype(F % "Regular", 25)
sm   = ImageFont.truetype(F % "Regular", 21)

x = 430
d.text((x, 258), "dead silicon", font=bold, fill=INK)
d.text((x, 366), "a from-scratch llm inference engine,", font=reg, fill=(23,24,27,190))
d.text((x, 400), "built on a gtx 1050 and 16gb of ram.", font=reg, fill=(23,24,27,190))


img.save("/mnt/user-data/outputs/website/og.png", optimize=True)
import os
print(f"og.png  {W}x{H}  {os.path.getsize('/mnt/user-data/outputs/website/og.png')/1024:.0f} kb")
