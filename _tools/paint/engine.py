"""engine.py — a small oil-paint simulator. no image model, nothing traced.

a painting here is a list of brush strokes. each stroke is a path, a width and a
colour, and the brush that makes it is a row of bristles: every bristle carries
its own load of paint, starts and lifts at its own point, and runs dry on its
own schedule, so a stroke comes out streaked, ragged at the ends, and broken
over the weave of the canvas where the paint gives out.

the canvas keeps three things per pixel: colour, the height of the paint (so the
finished picture can be lit from the side like real impasto), and the number of
the stroke that last touched it (so the website can replay the painting in the
order it was made).

needs numpy and opencv. everything is seeded: the same seed paints the same
picture, stroke for stroke.
"""
import math
import numpy as np
import cv2

F = np.float32


def smooth(a, b, x):
    t = np.clip((x - a) / (b - a + 1e-9), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def bezier(p0, p1, p2, n=8):
    """a quadratic curve sampled into a polyline."""
    t = np.linspace(0, 1, n, dtype=F)[:, None]
    p0, p1, p2 = (np.asarray(p, F) for p in (p0, p1, p2))
    return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t * t * p2


def spline(pts, n=10):
    """catmull-rom through the points, sampled into a polyline."""
    p = np.asarray(pts, F)
    if len(p) < 3:
        return p
    p = np.vstack([2 * p[0] - p[1], p, 2 * p[-1] - p[-2]])
    out = []
    for i in range(1, len(p) - 2):
        t = np.linspace(0, 1, n, endpoint=False, dtype=F)[:, None]
        a, b, c, d = p[i - 1], p[i], p[i + 1], p[i + 2]
        out.append(0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t * t
                          + (-a + 3 * b - 3 * c + d) * t ** 3))
    out.append(p[-2][None, :])
    return np.vstack(out)


class Mask:
    """a region strokes can be held inside: a polygon with a slightly unsteady edge."""

    def __init__(self, poly, W, H, feather=0.8, grow=0.0):
        poly = np.asarray(poly, F)
        pad = 4 + grow
        self.x0 = int(max(0, math.floor(poly[:, 0].min() - pad)))
        self.y0 = int(max(0, math.floor(poly[:, 1].min() - pad)))
        self.x1 = int(min(W, math.ceil(poly[:, 0].max() + pad)))
        self.y1 = int(min(H, math.ceil(poly[:, 1].max() + pad)))
        self.ok = self.x1 > self.x0 and self.y1 > self.y0
        if not self.ok:
            return
        m = np.zeros((self.y1 - self.y0, self.x1 - self.x0), np.uint8)
        q = np.round((poly - [self.x0, self.y0]) * 16).astype(np.int32)
        cv2.fillPoly(m, [q], 255, lineType=cv2.LINE_AA, shift=4)
        if grow > 0:
            k = int(grow) * 2 + 1
            m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
        m = m.astype(F) / 255.0
        if feather > 0:
            m = cv2.GaussianBlur(m, (0, 0), feather)
        self.m = m


class Canvas:
    def __init__(self, W, H, ground, seed=1):
        self.W, self.H = W, H
        self.rng = np.random.default_rng(seed)
        self.rgb = np.empty((H, W, 3), F)
        self.rgb[:] = np.asarray(ground, F)
        self.ground = np.asarray(ground, F)
        self.h = np.zeros((H, W), F)
        self.order = np.zeros((H, W), F)
        self.n = 0
        self.frame = None          # where paint may land; outside it the ground shows
        self.tooth = self._tooth()

    def _tooth(self):
        """the weave of the cloth plus the unevenness of the priming, 0..1."""
        r, H, W = self.rng, self.H, self.W
        n = r.random((H, W), dtype=F)
        a = cv2.GaussianBlur(n, (0, 0), 1.1)
        b = cv2.GaussianBlur(n, (0, 0), 5.0)
        yy, xx = np.mgrid[0:H, 0:W].astype(F)
        weave = (np.sin(xx * 2 * np.pi / 3.3 + np.sin(yy / 41.0) * 1.3)
                 * np.sin(yy * 2 * np.pi / 3.1 + np.sin(xx / 37.0) * 1.3))
        t = 0.6 * (a - a.mean()) / a.std() + 0.5 * (b - b.mean()) / b.std() + 0.45 * weave
        lo, hi = np.percentile(t, [1, 99])
        return np.clip((t - lo) / (hi - lo), 0, 1).astype(F)

    # ------------------------------------------------------------------ strokes
    def stroke(self, pts, width, color, alpha=1.0, dry=0.3, soft=0.14, jitter=0.05,
               nb=None, taper=(0.10, 0.22), thick=1.0, clip=None, rag=None,
               scumble=0.0, pickup=0.0, glaze=False, free=False):
        """one pull of the brush along pts.

        dry      how soon the bristles run out (0 loaded, 1 nearly empty)
        soft     how soft the long edges are, as a fraction of the half width
        jitter   how much the bristles differ in colour
        rag      how uneven the two ends are, in pixels
        scumble  dry-brush from the first touch: paint only catches the weave
        pickup   how much wet colour already on the canvas the brush drags along
        glaze    a thin transparent layer: tints, leaves no relief
        free     ignore the painted area's edge (the pencil does; the brush doesn't)
        """
        r = self.rng
        pts = np.asarray(pts, F)
        if len(pts) < 2:
            return
        hw = max(0.6, width * 0.5)
        rag = width * 0.4 if rag is None else rag
        pad = hw + 3 + rag
        x0 = int(max(0, math.floor(pts[:, 0].min() - pad)))
        x1 = int(min(self.W, math.ceil(pts[:, 0].max() + pad)))
        y0 = int(max(0, math.floor(pts[:, 1].min() - pad)))
        y1 = int(min(self.H, math.ceil(pts[:, 1].max() + pad)))
        if clip is not None:
            if not clip.ok:
                return
            x0, y0, x1, y1 = max(x0, clip.x0), max(y0, clip.y0), min(x1, clip.x1), min(y1, clip.y1)
        if x1 <= x0 or y1 <= y0:
            return
        X = np.arange(x0, x1, dtype=F)[None, :]
        Y = np.arange(y0, y1, dtype=F)[:, None]
        seg = pts[1:] - pts[:-1]
        L = np.hypot(seg[:, 0], seg[:, 1])
        Lt = float(L.sum())
        if Lt < 0.5:
            return
        shp = (y1 - y0, x1 - x0)
        bd2 = np.full(shp, 1e12, F)
        bu = np.zeros(shp, F)
        bs = np.ones(shp, F)
        cum, ns = 0.0, len(seg)
        for i in range(ns):
            l = float(L[i])
            if l < 1e-3:
                continue
            ax, ay = pts[i]
            dx, dy = seg[i]
            px, py = X - ax, Y - ay
            t = (px * dx + py * dy) / (l * l)
            t = np.clip(t, -1e3 if i == 0 else 0.0, 1e3 if i == ns - 1 else 1.0)
            ex, ey = px - t * dx, py - t * dy
            d2 = ex * ex + ey * ey
            m = d2 < bd2
            bd2 = np.where(m, d2, bd2)
            bu = np.where(m, cum + t * l, bu)
            bs = np.where(m, np.where(px * dy - py * dx < 0, -1.0, 1.0), bs)
            cum += l
        dist = np.sqrt(bd2)
        un = bu / Lt
        # the brush opens as it lands and closes as it lifts
        half = hw * (0.72 + 0.28 * smooth(0.0, taper[0], un)) * (1.0 - 0.38 * smooth(1.0 - taper[1], 1.0, un))
        across = dist / half
        nbr = nb or int(np.clip(width / 2.4, 2, 48))
        bi = np.clip(((dist * bs / half) * 0.5 + 0.5) * nbr, 0, nbr - 1).astype(np.int32)

        def per_bristle(scale=1.0, smoothk=1):
            v = r.standard_normal(nbr).astype(F) * scale
            if smoothk and nbr > 3:
                v = np.convolve(np.pad(v, 1, mode="edge"), [0.25, 0.5, 0.25], mode="valid").astype(F)
            return v

        start = (r.random(nbr).astype(F) - 0.3) * rag
        end = Lt - (r.random(nbr).astype(F) * 1.5 - 0.3) * rag
        load = (1.30 - dry * (0.20 + 1.3 * r.random(nbr))).astype(F)   # where along the stroke it runs out
        a = 1.0 - smooth(1.0 - soft, 1.0, across)
        a = a * smooth(start[bi] - 1.5, start[bi] + 1.5, bu) * (1.0 - smooth(end[bi] - 2.5, end[bi] + 1.5, bu))
        # as a bristle runs out the paint only catches the high points of the weave
        thin = smooth(load[bi] - 0.35, load[bi] + 0.15, un)
        thr = np.maximum(thin * 0.95, scumble)
        tp = self.tooth[y0:y1, x0:x1] * 0.85 + 0.12 + 0.05 * per_bristle()[bi]
        a = a * (1.0 - smooth(tp - 0.10, tp + 0.10, thr))
        a = a * alpha
        if clip is not None:
            a = a * clip.m[y0 - clip.y0:y1 - clip.y0, x0 - clip.x0:x1 - clip.x0]
        if self.frame is not None and not free:
            a = a * self.frame[y0:y1, x0:x1]
        if not np.any(a > 0.003):
            return
        col = np.asarray(color, F)
        reg = self.rgb[y0:y1, x0:x1]
        if pickup > 0:
            wsum = float(a.sum()) + 1e-6
            under = (reg * a[..., None]).sum(axis=(0, 1)) / wsum
            col = col * (1 - pickup) + under * pickup
        tint = (1.0 + jitter * per_bristle(1.0)[bi])[..., None]
        reg[:] = reg * (1 - a[..., None]) + np.clip(col * tint, 0, 1.2) * a[..., None]
        if not glaze:
            ridge = 0.62 + 0.38 * (0.5 + 0.5 * np.tanh(per_bristle(1.0, 0)[bi]))
            bead = 0.45 * smooth(0.55, 0.9, across) * (1.0 - smooth(0.92, 1.0, across))
            hh = self.h[y0:y1, x0:x1]
            hh[:] = hh * (1 - a) + a * thick * (ridge + bead) * (1.0 - 0.5 * thin)
        self.n += 1
        self.order[y0:y1, x0:x1][a > 0.35] = self.n

    def line(self, p, q, width, color, bow=0.0, **kw):
        """a stroke between two points, bowed a little the way an arm draws it."""
        p, q = np.asarray(p, F), np.asarray(q, F)
        d = q - p
        n = np.array([-d[1], d[0]], F)
        mid = (p + q) * 0.5 + n * bow
        self.stroke(bezier(p, mid, q, 6) if abs(bow) > 1e-4 else np.stack([p, q]), width, color, **kw)

    def dab(self, x, y, size, color, ang=None, stretch=1.6, **kw):
        """a short touch of the brush."""
        ang = self.rng.uniform(0, math.pi) if ang is None else ang
        l = size * stretch * 0.5
        c, s = math.cos(ang) * l, math.sin(ang) * l
        kw.setdefault("rag", size * 0.25)
        kw.setdefault("taper", (0.25, 0.3))
        self.stroke([(x - c, y - s), (x + c, y + s)], size, color, **kw)

    def fill(self, poly, color, ang, width, length, density=1.0, clip=True, angjit=0.12,
             coljit=0.05, bow=0.06, order="random", grow=0.0, feather=0.8, inset=0.0, **kw):
        """cover a polygon with strokes laid in one direction.

        color, ang and width can each be a function of (x, y) so the strokes can
        follow a form or a light. with clip the edge of the shape is kept clean
        while the brushwork inside stays loose.
        """
        r = self.rng
        poly = np.asarray(poly, F)
        if poly.ndim != 2 or len(poly) < 3:      # nothing of this shape is in the picture
            return
        mk = Mask(poly, self.W, self.H, feather=feather, grow=grow)
        if not mk.ok:
            return
        w0 = width if not callable(width) else width(*poly.mean(axis=0))
        a0 = ang if not callable(ang) else ang(*poly.mean(axis=0))
        # lay the stroke centres on a grid turned to the stroke direction, then shake it
        c, s = math.cos(a0), math.sin(a0)
        cx, cy = poly.mean(axis=0)
        rel = poly - [cx, cy]
        along = rel[:, 0] * c + rel[:, 1] * s
        cross = -rel[:, 0] * s + rel[:, 1] * c
        da = max(2.0, length * 0.55 / density)
        dc = max(1.0, w0 * 0.5 / density)
        us = np.arange(along.min() - da * 0.5, along.max() + da, da)
        vs = np.arange(cross.min() - dc * 0.5, cross.max() + dc, dc)
        U, V = np.meshgrid(us, vs)
        U = U + (r.random(U.shape) - 0.5) * da * 1.0
        V = V + (r.random(V.shape) - 0.5) * dc * 0.9
        px = (cx + U * c - V * s).ravel()
        py = (cy + U * s + V * c).ravel()
        cnt = poly.reshape(-1, 1, 2).astype(F)
        keep = [i for i in range(len(px))
                if cv2.pointPolygonTest(cnt, (float(px[i]), float(py[i])), True) > -(w0 * 0.35) + inset]
        if order == "random":
            r.shuffle(keep)
        elif callable(order):
            keep.sort(key=lambda i: order(px[i], py[i]))
        for i in keep:
            x, y = float(px[i]), float(py[i])
            a = (ang(x, y) if callable(ang) else ang) + r.normal(0, angjit)
            w = (width(x, y) if callable(width) else width) * r.uniform(0.8, 1.2)
            l = length * r.uniform(0.6, 1.3) * 0.5
            col = np.asarray(color(x, y) if callable(color) else color, F)
            if col is None:
                continue
            col = col * (1.0 + r.normal(0, coljit)) + r.normal(0, coljit * 0.35, 3)
            dx, dy = math.cos(a) * l, math.sin(a) * l
            self.line((x - dx, y - dy), (x + dx, y + dy), w, col, bow=r.normal(0, bow),
                      clip=mk if clip else None, **kw)

    # ---------------------------------------------------------------- finishing
    def paint_frame(self, margin, seed=11):
        """decide where the picture stops: brush a block of paint on a spare canvas
        and keep its shape, so the picture ends in bristle marks, not a ruled edge."""
        t = Canvas(self.W, self.H, (0, 0, 0), seed)
        m, W, H = margin, self.W, self.H
        for (a, b, ang) in [((m, m), (W - m, m), 0.03), ((W - m, H - m), (m, H - m), -0.02),
                            ((m, H - m), (m, m), 1.55), ((W - m, m), (W - m, H - m), 1.60)]:
            a, b = np.asarray(a, F), np.asarray(b, F)
            d = (b - a) / np.linalg.norm(b - a)
            n = np.array([-d[1], d[0]], F)             # points into the picture
            poly = [a - d * m * 0.2 + n * m * -0.15, b + d * m * 0.2 + n * m * -0.15,
                    b + d * m * 0.2 + n * m * 2.6, a - d * m * 0.2 + n * m * 2.6]
            t.fill(poly, (1, 1, 1), ang, m * 1.5, m * 7, density=1.6, clip=False, angjit=0.07, coljit=0,
                   jitter=0, dry=0.55, inset=m * 0.5)
        f = np.clip(t.rgb[..., 0], 0, 1)
        f[int(m * 2.4):H - int(m * 2.4), int(m * 2.4):W - int(m * 2.4)] = 1.0
        self.frame = np.clip(cv2.GaussianBlur(f, (0, 0), 0.6), 0, 1)

    def render(self, relief=0.42, light=(-0.55, -0.83), weave=0.05, grain=0.012):
        """light the paint from the upper left, the way a picture hangs under a lamp."""
        h = cv2.GaussianBlur(self.h, (0, 0), 0.75)
        gx = cv2.Sobel(h, cv2.CV_32F, 1, 0, ksize=3) / 8.0
        gy = cv2.Sobel(h, cv2.CV_32F, 0, 1, ksize=3) / 8.0
        s = gx * light[0] + gy * light[1]
        shade = 1.0 + relief * np.tanh(s * 2.6)
        spec = np.clip(s * 2.2 - 0.55, 0, 1) * 0.10 * relief
        out = self.rgb * shade[..., None] + spec[..., None]
        out = out * (1.0 + weave * (self.tooth - 0.5))[..., None]
        if grain:
            g = np.random.default_rng(99).standard_normal((self.H, self.W)).astype(F)
            out = out + (cv2.GaussianBlur(g, (0, 0), 0.6) * grain)[..., None]
        return np.clip(out, 0, 1)

    def save(self, path, **kw):
        img = (self.render(**kw) * 255 + 0.5).astype(np.uint8)
        cv2.imwrite(path, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))

    def order_map(self, lo=0, hi=None):
        """0..1 per pixel: when it was last painted, between stroke lo and stroke hi."""
        hi = self.n if hi is None else hi
        return np.clip((self.order - lo) / max(1, hi - lo), 0, 1)


def hexc(s):
    s = s.lstrip("#")
    return np.array([int(s[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], F)
