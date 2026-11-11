"""world.py — just enough of a room for a painter to stand in.

a camera, boxes, and lamps. nothing here draws: it answers two questions the
painter keeps asking — "where on the canvas is this corner?" and "how much light
reaches this spot, and what colour is it?". shadows are real: a spot is dark
because something stands between it and the lamp.
"""
import math
import numpy as np

D = np.float64


def V(*a):
    return np.array(a, D)


def unit(v):
    return v / (np.linalg.norm(v) + 1e-12)


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], D)


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], D)


class Cam:
    def __init__(self, pos, look, hfov, W, H, shift=(0.0, 0.0)):
        self.pos, self.W, self.H = np.asarray(pos, D), W, H
        self.f = unit(np.asarray(look, D) - self.pos)
        self.r = unit(np.cross(self.f, V(0, 1, 0)))
        self.u = np.cross(self.r, self.f)
        self.k = (W / 2) / math.tan(math.radians(hfov) / 2)
        self.cx, self.cy = W / 2 + shift[0] * W, H / 2 + shift[1] * H

    def p(self, P):
        d = np.asarray(P, D) - self.pos
        z = max(1e-6, float(d @ self.f))
        return (self.cx + self.k * float(d @ self.r) / z, self.cy - self.k * float(d @ self.u) / z)

    def depth(self, P):
        return float((np.asarray(P, D) - self.pos) @ self.f)

    def px(self, P, metres):
        """how many pixels a length is, at the distance of P."""
        return self.k * metres / max(1e-6, self.depth(P))

    def ray(self, x, y):
        return unit(self.f * self.k + self.r * (x - self.cx) - self.u * (y - self.cy))

    def on_plane(self, x, y, P0, N):
        """the point of a plane that sits under a pixel."""
        d = self.ray(x, y)
        den = float(d @ N)
        if abs(den) < 1e-9:
            return None
        t = float((np.asarray(P0, D) - self.pos) @ N) / den
        return self.pos + d * t if t > 0 else None


FACES = {  # name: (normal axis, sign, corner signs in order tl, tr, br, bl as seen from outside)
    "+y": (1, 1, [(-1, 1, -1), (1, 1, -1), (1, 1, 1), (-1, 1, 1)]),
    "-y": (1, -1, [(-1, -1, 1), (1, -1, 1), (1, -1, -1), (-1, -1, -1)]),
    "+z": (2, 1, [(-1, 1, 1), (1, 1, 1), (1, -1, 1), (-1, -1, 1)]),
    "-z": (2, -1, [(1, 1, -1), (-1, 1, -1), (-1, -1, -1), (1, -1, -1)]),
    "+x": (0, 1, [(1, 1, 1), (1, 1, -1), (1, -1, -1), (1, -1, 1)]),
    "-x": (0, -1, [(-1, 1, -1), (-1, 1, 1), (-1, -1, 1), (-1, -1, -1)]),
}


class Box:
    """a box that can be turned (yaw) and leaned (pitch)."""

    def __init__(self, c, size, yaw=0.0, pitch=0.0, R=None, shadow=True):
        self.c = np.asarray(c, D)
        self.h = np.asarray(size, D) / 2
        self.R = R if R is not None else rot_y(yaw) @ rot_x(pitch)
        self.shadow = shadow
        self._c = tuple(self.c)
        self._ax = [tuple(self.R[:, i]) for i in range(3)]
        self._h = tuple(self.h)

    def at(self, lx, ly, lz):
        """a point given in the box's own coordinates, -1..1 on each axis."""
        return self.c + self.R @ (np.array([lx, ly, lz], D) * self.h)

    def face(self, name):
        ax, sg, cs = FACES[name]
        return [self.at(*c) for c in cs], self.R[:, ax] * sg

    def visible(self, cam):
        out = []
        for name in FACES:
            q, n = self.face(name)
            ctr = sum(q) / 4
            if float((cam.pos - ctr) @ n) > 1e-6:
                out.append((name, q, n))
        return out

    def blocks(self, o, d):
        """does the segment o -> o+d pass through the box?"""
        px, py, pz = o[0] - self._c[0], o[1] - self._c[1], o[2] - self._c[2]
        t0, t1 = 1e-4, 1.0
        for (ax, ay, az), h in zip(self._ax, self._h):
            ol = px * ax + py * ay + pz * az
            dl = d[0] * ax + d[1] * ay + d[2] * az
            if abs(dl) < 1e-10:
                if abs(ol) > h:
                    return False
                continue
            a, b = (-h - ol) / dl, (h - ol) / dl
            if a > b:
                a, b = b, a
            if a > t0:
                t0 = a
            if b < t1:
                t1 = b
            if t0 > t1:
                return False
        return True


class Lamp:
    def __init__(self, pos, color, radius=0.03, shadow=True, facing=None, wrap=0.25):
        self.pos, self.color = np.asarray(pos, D), np.asarray(color, D)
        self.radius, self.shadow, self.wrap = radius, shadow, wrap
        self.facing = None if facing is None else unit(np.asarray(facing, D))


class Scene:
    def __init__(self, seed=5):
        self.lamps, self.boxes = [], []
        self.amb_up = V(0.05, 0.07, 0.15)      # light from above (ceiling, sky)
        self.amb_dn = V(0.03, 0.04, 0.09)      # light from below
        self.exposure = 1.5
        self.chroma = 1.0
        self.haze = V(0, 0, 0)                 # a floor under the darks, so shadows keep a colour
        self.sun = None                        # (travel direction, colour, gate) for daylight
        self.rng = np.random.default_rng(seed)

    def add(self, box):
        self.boxes.append(box)
        return box

    def seen(self, P, L, samples=5):
        """the share of a lamp that a point can see, 0..1."""
        if not L.shadow:
            return 1.0
        vis, r = 0, self.rng
        for i in range(samples):
            lp = L.pos if i == 0 else L.pos + r.normal(0, L.radius, 3)
            d = (lp[0] - P[0], lp[1] - P[1], lp[2] - P[2])
            if not any(b.shadow and b.blocks(P, d) for b in self.boxes):
                vis += 1
        return vis / samples

    def light(self, P, N, samples=5, gloss=0.0, view=None):
        """the light arriving at P on a surface facing N, as rgb."""
        P = np.asarray(P, D)
        Po = P + N * 0.004
        up = 0.5 + 0.5 * N[1]
        tot = self.amb_up * up + self.amb_dn * (1 - up)
        spec = np.zeros(3, D)
        for L in self.lamps:
            l = L.pos - P
            d2 = float(l @ l)
            l = l / math.sqrt(d2)
            nd = (float(N @ l) + L.wrap) / (1 + L.wrap)
            if nd <= 0:
                continue
            e = 1.0
            if L.facing is not None:
                e = max(0.0, float(-l @ L.facing))
                if e <= 0:
                    continue
            v = self.seen(Po, L, samples)
            if v <= 0:
                continue
            tot = tot + L.color * (nd * e * v / (d2 + 0.015))
            if gloss > 0 and view is not None:
                hv = unit(l + unit(view - P))
                spec = spec + L.color * (max(0.0, float(N @ hv)) ** 60) * gloss * v / (d2 + 0.015)
        if self.sun is not None:
            sd, sc, gate = self.sun
            nd = float(N @ -sd)
            if nd > 0 and abs(sd[2]) > 1e-6:
                t = Po[2] / sd[2]
                Q = Po - sd * t
                g = gate(Q[0], Q[1]) if t > 0 else 0.0
                if g > 0:
                    d = tuple(-sd * t)
                    if not any(b.shadow and b.blocks(Po, d) for b in self.boxes):
                        tot = tot + sc * nd * g
                        if gloss > 0 and view is not None:
                            hv = unit(-sd + unit(view - P))
                            spec = spec + sc * (max(0.0, float(N @ hv)) ** 40) * gloss * g
        return tot, spec

    def tone(self, x):
        x = np.maximum(np.asarray(x, D), 0)
        c = 1.0 - np.exp(-x * self.exposure)
        c = c + self.haze * (1 - c)
        g = float(c @ V(0.30, 0.59, 0.11))             # a painter mixes cleaner than a lamp does
        c = np.clip(g + (c - g) * self.chroma, 0, 1)
        return c.astype(np.float32)

    def shade(self, P, N, albedo, samples=5, gloss=0.0, view=None, emit=None):
        lt, sp = self.light(P, N, samples, gloss, view)
        x = np.asarray(albedo, D) * lt + sp
        if emit is not None:
            x = x + np.asarray(emit, D)
        return self.tone(x)
