#!/usr/bin/env python3
"""garden.py — the painting on the garden page.

    python3 _tools/paint/garden.py                 paint everything the page uses
    python3 _tools/paint/garden.py night wide --preview out.png --scale 0.5

the garden is a planter with a glass front, the kind used to watch roots grow. it
stands on the bench under the same lamp. every note in data.js gets a stake and
whatever has come up beside it:

    seed        a seed just under the surface. nothing above ground but the stake
    growing     a seedling
    evergreen   a small conifer

and every link in data.js is a pale thread of fungus running under the soil from
one note to the other (an edge is a claim; this is the claim, drawn). the longer
the reach, the deeper it runs, so the threads never tangle.

the notes stand in the order that keeps linked notes nearest each other. the page
gets told where every stake and every thread ended up (art/garden.js), so it can
make the stakes clickable and light a note's threads when you point at it.

it reads data.js, so the picture is only right on the day it was painted:
`_tools/ds paint` after planting, tending or linking.
"""
import itertools
import json
import math
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Canvas, bezier, spline, hexc, smooth, F                 # noqa: E402
from world import Scene, V                                                # noqa: E402
from bench import GROUND, ROOT, save, write_assets, circle                # noqa: E402

VIEWS = {  # canvas w, h, brush scale, saved size
    "wide": (2400, 1050, 1.0, (2000, 875)),
    "tall": (1500, 1300, 0.9, (1000, 867)),
    "sprite": (520, 600, 0.62, (260, 300)),        # one plant, for the key under the picture
}
WALL_N, WALL_D = (0.70, 0.76, 0.66), (0.50, 0.74, 0.66)
WOOD, STAKE, TAG = (0.50, 0.31, 0.17), (0.74, 0.62, 0.42), (0.93, 0.91, 0.83)
THREAD = (0.97, 0.93, 0.78)
SOILS = [(0.20, 0.125, 0.075), (0.34, 0.215, 0.12), (0.55, 0.225, 0.115), (0.41, 0.265, 0.17)]   # topsoil ... laterite ... clay


def load():
    src = open(os.path.join(ROOT, "data.js"), encoding="utf-8").read()
    g = json.loads(src[src.index("window.DS=") + 10:].rstrip().rstrip(";"))["garden"]
    return g["notes"], [tuple(l) for l in g["links"]]


def arrange(notes, links):
    """the order along the soil that keeps linked notes closest. up to eight notes
    every order is tried; past that they stay in the order they were sown."""
    ids = [n["id"] for n in notes]
    if len(ids) > 8 or len(ids) < 3:
        return ids
    best, cost = ids, 1e9
    for perm in itertools.permutations(ids):
        pos = {k: i for i, k in enumerate(perm)}
        c = sum(abs(pos[a] - pos[b]) for a, b in links if a in pos and b in pos)
        if c < cost:
            best, cost = list(perm), c
    return best


class Bed:
    def __init__(self, mode="night", view="wide", scale=1.0, only=None):
        self.mode, self.view, self.night = mode, view, mode == "night"
        W, H, k, self.out = VIEWS[view]
        self.S = S = scale * k
        self.W, self.H = W, H = int(W * scale), int(H * scale)
        self.cv = Canvas(W, H, hexc(GROUND[mode]), seed=17)
        self.r = self.cv.rng
        self.pencil = hexc("7f8bb8") if self.night else hexc("5b5f6e")
        sc = self.sc = Scene()
        if self.night:
            sc.exposure, sc.chroma, sc.haze = 1.45, 1.38, V(0.035, 0.050, 0.115)
        else:
            sc.exposure, sc.chroma, sc.haze = 1.6, 1.45, V(0.03, 0.04, 0.07)
        if only:                                    # the key: one plant of one kind
            self.notes, self.links = [{"id": "x", "status": only}], []
        else:
            self.notes, self.links = load()
        self.status = {n["id"]: n["status"] for n in self.notes}
        self.order = arrange(self.notes, self.links)
        self.links = [l for l in self.links if l[0] in self.status and l[1] in self.status]
        tall, sprite = view == "tall", view == "sprite"
        self.bx0, self.bx1 = (W * 0.05, W * 0.95) if not sprite else (-W * 0.3, W * 1.3)
        self.rt = H * (0.36 if not tall else 0.31)          # top of the top rail
        if sprite:
            self.rt = H * 0.56
        self.rh = H * 0.045
        self.gt = self.rt + self.rh                         # top of the glass
        self.gb = H * 0.865 if not sprite else H * 1.3      # bottom of the glass
        self.dk = self.gb + H * 0.045                       # where the bench starts
        self.pw = W * (0.03 if tall else 0.02)
        self.ix0, self.ix1 = self.bx0 + self.pw, self.bx1 - self.pw
        if sprite:
            self.ix0, self.ix1 = 0, W
        n = len(self.order)
        self.px = {k_: self.ix0 + (i + 0.5) / n * (self.ix1 - self.ix0) for i, k_ in enumerate(self.order)}
        self.sd = (self.gb if not sprite else H) - self.soil(W / 2)     # depth of soil you can see
        # the lamp hangs in at the left end; in the key it is out of the picture
        self.bulb = (W * 0.2, -H * 0.4) if sprite else (W * (0.14 if tall else 0.115), H * (0.13 if tall else 0.15))
        self.tag, self.paths = {}, []

    # ------------------------------------------------------------------- light
    def soil(self, x):
        return self.gt + self.H * 0.036 + self.H * 0.006 * math.sin(x / (53 * self.S)) + self.H * 0.004 * math.sin(x / (17 * self.S) + 1)

    def light(self, x, y, k=1.0):
        if self.night:
            d = math.hypot(x - self.bulb[0], y - self.bulb[1])
            return V(0.046, 0.088, 0.24) + V(1.0, 0.76, 0.44) * (2.4 / (1 + (d / (0.75 * self.H)) ** 2)) * k
        d = math.hypot(x + 0.2 * self.W, y - 0.1 * self.H)
        return V(0.52, 0.63, 0.80) * 1.2 + V(0.80, 0.92, 1.0) * (0.55 / (1 + (d / (0.9 * self.H)) ** 2)) * k

    def col(self, albedo, x, y, k=1.0):
        return self.sc.tone(V(*albedo) * self.light(x, y, k))

    def away(self, x, y, m):
        """where a thing's shadow falls on the wall behind it: straight away from the lamp."""
        if self.night:
            dx, dy = x - self.bulb[0], y - self.bulb[1]
            d = math.hypot(dx, dy)
            return dx / d * m, dy / d * m
        return m * 0.9, m * 0.35

    def sketch(self, a, b, alpha=0.8):
        a, b = np.asarray(a, F), np.asarray(b, F)
        d = b - a
        self.cv.line(a - d * 0.03, b + d * 0.03, 2.1 * self.S, self.pencil, bow=self.r.normal(0, 0.005), alpha=alpha, dry=0.4,
                     scumble=0.22, jitter=0, nb=2, free=True, glaze=True, soft=0.5, rag=3)

    # -------------------------------------------------------------- the pencil
    def underdrawing(self):
        W, H, cv = self.W, self.H, self.cv
        for y in (self.rt, self.gt, self.gb, self.dk):
            self.sketch((self.bx0 - W * 0.01, y), (self.bx1 + W * 0.01, y))
        for x in (self.bx0, self.ix0, self.ix1, self.bx1):
            self.sketch((x, self.rt), (x, self.dk))
        self.sketch((0, self.dk), (W, self.dk), alpha=0.4)
        pts = [(x, self.soil(x)) for x in np.linspace(self.ix0, self.ix1, 30)]
        cv.stroke(np.array(pts, F), 1.9 * self.S, self.pencil, alpha=0.6, scumble=0.2, nb=2, free=True, glaze=True, jitter=0)
        for k_ in self.order:
            x = self.px[k_]
            self.sketch((x, self.rt - H * 0.17), (x, self.soil(x) + H * 0.08), alpha=0.35)
        for a, b, path in self.thread_paths():
            cv.stroke(np.array(path, F), 1.6 * self.S, self.pencil, alpha=0.4, scumble=0.25, nb=2, free=True, glaze=True, jitter=0)

    # ---------------------------------------------------------------- the room
    def wall(self, fine=False):
        W, H, S, cv = self.W, self.H, self.S, self.cv
        alb = WALL_N if self.night else WALL_D
        rad = 0.9 * H

        def ang(x, y):
            dx, dy = x - self.bulb[0], y - self.bulb[1]
            ring = math.atan2(dy, dx) + math.pi / 2
            k = float(smooth(2.0, 0.5, math.hypot(dx, dy) / rad)) if self.night else 0.0
            flat = -0.42 + 0.25 * math.sin(x / (300 * S))
            return math.atan2(k * math.sin(ring) + (1 - k) * math.sin(flat), k * math.cos(ring) + (1 - k) * math.cos(flat))

        def c(x, y):
            damp = 0.5 + 0.5 * math.sin(x / (210 * S) + 1.3 * math.sin(y / (160 * S))) * math.sin(y / (280 * S) + x / (700 * S))
            return self.col(alb, x, y) * (0.88 + 0.12 * damp)
        low = min(H + 40, self.dk + 6)                # the wall runs on down behind the planter
        poly = [(-40, -40), (W + 40, -40), (W + 40, low), (-40, low)]
        if not fine:
            cv.fill(poly, c, ang, 54 * S, 175 * S, density=1.35, dry=0.14, coljit=0.035, feather=0)
        else:
            cv.fill(poly, c, ang, 30 * S, 96 * S, density=0.62, dry=0.36, coljit=0.05, feather=0, pickup=0.3)

    def bench(self):
        W, H, S, cv = self.W, self.H, self.S, self.cv
        poly = [(-40, self.dk), (W + 40, self.dk), (W + 40, H + 40), (-40, H + 40)]
        cv.fill(poly, lambda x, y: self.col((0.46, 0.285, 0.165), x, y, 0.9), 0.0, 30 * S, 180 * S, density=1.35, dry=0.14,
                coljit=0.04, angjit=0.03, feather=0)
        cv.fill(poly, lambda x, y: self.col((0.46, 0.285, 0.165), x, y, 0.9), 0.0, 14 * S, 70 * S, density=0.8, dry=0.4,
                coljit=0.055, angjit=0.03, feather=0, pickup=0.2)
        # the planter's own shadow on the wood
        cv.line((self.bx0 - W * 0.01, self.dk + 5 * S), (self.bx1 + W * 0.03, self.dk + 7 * S), 15 * S,
                self.sc.tone(V(0.02, 0.022, 0.05)), alpha=0.85, dry=0.3, rag=24 * S)

    def frame(self):
        """the planter: a top rail, a bottom rail and two posts, with glass between."""
        W, H, S, cv = self.W, self.H, self.S, self.cv
        ov = W * 0.008
        c = lambda x, y: self.col(WOOD, x, y)                                         # noqa: E731
        parts = [((self.bx0 - ov, self.rt, self.bx1 + ov, self.gt), 0.0), ((self.bx0 - ov, self.gb, self.bx1 + ov, self.dk), 0.0),
                 ((self.bx0, self.gt, self.ix0, self.gb), 1.57), ((self.ix1, self.gt, self.bx1, self.gb), 1.57)]
        for (x0, y0, x1, y1), a in parts:
            cv.fill([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], c, a, 13 * S, 130 * S, density=1.4, dry=0.2, coljit=0.045,
                    angjit=0.025)
        # the lit top edge of each rail, the shadow under the top one
        for y in (self.rt + 2 * S, self.gb + 2 * S):
            cv.line((self.bx0 - ov, y), (self.bx1 + ov, y), 3 * S, self.col((0.80, 0.56, 0.34), W * 0.3, y), alpha=0.8, dry=0.45)
        for x in (self.bx0 + self.pw * 0.5, self.bx1 - self.pw * 0.5):                 # screws
            for y in (self.rt + self.rh * 0.5, self.gb + self.rh * 0.5):
                cv.dab(x, y, 7 * S, self.sc.tone(V(0.03, 0.03, 0.04)), stretch=1.0)
                cv.dab(x - 1.5 * S, y - 1.5 * S, 2.6 * S, self.col((0.8, 0.8, 0.8), x, y), stretch=1.0)

    # ---------------------------------------------------------------- the soil
    def bands(self):
        """the layers, top to bottom, each as its outline."""
        xs = np.linspace(self.ix0 - 4, self.ix1 + 4, 34)
        cuts = [0.0, 0.20, 0.47, 0.76, 1.0]
        S, H = self.S, self.H
        base = self.gb if self.view != "sprite" else H + 40

        def edge(j):
            if j == 0:
                return [self.soil(x) for x in xs]
            if j == len(cuts) - 1:
                return [base + 4 for x in xs]
            return [self.soil(x) + (base - self.soil(x)) * cuts[j] + H * 0.016 * math.sin(x / (140 * S) + j * 2.1)
                    + H * 0.008 * math.sin(x / (47 * S) + j) for x in xs]
        out = []
        for j in range(len(cuts) - 1):
            top, bot = edge(j), edge(j + 1)
            out.append([(x, y) for x, y in zip(xs, top)] + [(x, y) for x, y in zip(xs[::-1], bot[::-1])])
        return out

    def earth(self, fine=False):
        W, H, S, cv = self.W, self.H, self.S, self.cv
        if not fine:                                                     # the dark inside of the box, above the soil
            cv.fill([(self.ix0, self.gt), (self.ix1, self.gt), (self.ix1, self.gt + H * 0.06), (self.ix0, self.gt + H * 0.06)],
                    lambda x, y: self.col((0.10, 0.075, 0.06), x, y, 0.35), 0.0, 14 * S, 90 * S, density=1.3, dry=0.2)
        for j, poly in enumerate(self.bands()):
            alb = SOILS[j]
            c = lambda x, y, a=alb: self.col(a, x, y, 1.0)                             # noqa: E731
            wav = lambda x, y, j_=j: 0.10 * math.sin(x / (120 * S) + j_ * 2.1)          # noqa: E731
            if not fine:
                cv.fill(poly, c, wav, 30 * S, 150 * S, density=1.4, dry=0.16, coljit=0.05, feather=0.6)
            else:
                cv.fill(poly, c, wav, 13 * S, 62 * S, density=0.8, dry=0.45, coljit=0.085, feather=0.6, pickup=0.2)

    def stones(self):
        cv, S, r = self.cv, self.S, self.r
        for i in range(int(46 * (self.ix1 - self.ix0) / (2160 * S) + 4)):
            x = r.uniform(self.ix0 + 20 * S, self.ix1 - 20 * S)
            y = r.uniform(self.soil(x) + self.sd * 0.10, self.soil(x) + self.sd * 0.97)
            if y > self.H + 10:
                continue
            sz = r.uniform(6, 17) * S
            alb = [(0.52, 0.50, 0.46), (0.62, 0.50, 0.33), (0.36, 0.34, 0.33), (0.60, 0.33, 0.22)][int(r.integers(0, 4))]
            a = r.uniform(-0.4, 0.4)
            cv.dab(x, y, sz, self.col(alb, x, y, 0.8), ang=a, stretch=r.uniform(1.1, 1.7), dry=0.1, jitter=0.06)
            cv.dab(x - sz * 0.15, y - sz * 0.2, sz * 0.36, self.col(alb, x, y, 1.5) * 1.1, ang=a, stretch=1.6, alpha=0.7, dry=0.3)

    # ------------------------------------------------------------- the threads
    def seed_at(self, k_):
        x = self.px[k_]
        return x, self.soil(x) + self.H * 0.052

    def thread_paths(self):
        """one path per link, from the left note to the right one. the further apart
        two notes stand, the deeper their thread runs."""
        if self.paths:
            return self.paths
        r = np.random.default_rng(31)
        pos = {k_: i for i, k_ in enumerate(self.order)}
        far = max([abs(pos[a] - pos[b]) for a, b in self.links] + [1])
        base = self.gb if self.view != "sprite" else self.H
        for a, b in sorted(self.links, key=lambda l: abs(pos[l[0]] - pos[l[1]])):
            if pos[a] > pos[b]:
                a, b = b, a
            (xa, ya), (xb, yb) = self.seed_at(a), self.seed_at(b)
            span = abs(pos[b] - pos[a])
            floor = min(base - self.H * 0.035, ya + self.sd * (0.13 + 0.70 * (span / far) ** 0.8))
            # down from one seed, along its own level, up to the other; never quite straight
            n = 6 + span * 4
            ctl = []
            walk = 0.0
            for i in range(n + 1):
                t = i / n
                y = ya + (floor - ya) * math.sin(math.pi * t) ** 0.42
                w = 0 if i in (0, n) else 1
                walk = walk * 0.6 + r.normal(0, 9 * self.S)
                ctl.append((xa + (xb - xa) * (t + 0.035 * math.sin(2 * math.pi * t)) + r.normal(0, 9 * self.S) * w, y + walk * w))
            self.paths.append((a, b, [tuple(map(float, q)) for q in spline(ctl, 6)]))
        return self.paths

    def threads(self):
        cv, S, r = self.cv, self.S, self.r
        deg = {k_: sum(k_ in l for l in self.links) for k_ in self.order}
        seen, todo = set(), sorted(self.order, key=lambda k_: -deg[k_])[:1]
        ordered = []                                                     # it grows out from the busiest note
        paths = self.thread_paths()
        while todo:
            k_ = todo.pop(0)
            if k_ in seen:
                continue
            seen.add(k_)
            for a, b, path in paths:
                if k_ in (a, b) and (a, b) not in [(p[0], p[1]) for p in ordered]:
                    ordered.append((a, b, path if k_ == a else path[::-1]))
                    todo.append(b if k_ == a else a)
        for a, b, path in ordered:
            p = np.array(path, F)
            step = 5
            for i in range(0, len(p) - 1, step):
                seg = p[i:i + step + 1]
                mx, my = seg[len(seg) // 2]
                c = self.col(THREAD, mx, my, 1.0) * (1.0 if self.night else 0.96)
                cv.stroke(seg, 5.2 * S, c, dry=0.12, jitter=0.03, rag=2 * S, soft=0.3, taper=(0.02, 0.02), thick=1.3)
                # a cord is several hyphae lying together: a second one wanders alongside
                off = np.array([r.normal(0, 4.5 * S), r.normal(0, 4.5 * S)], F)
                cv.stroke(seg + off, 2.4 * S, c * 0.94, alpha=0.8, dry=0.3, jitter=0.03, rag=3 * S, soft=0.3)
                ends = min(i, len(p) - 1 - i) < 12                         # they fan out where they meet a seed
                if r.random() < (0.95 if ends else 0.6):                                    # side hyphae, feeling about
                    a0 = math.atan2(seg[-1][1] - seg[0][1], seg[-1][0] - seg[0][0]) + r.choice([-1, 1]) * r.uniform(0.6, 1.2)
                    L = r.uniform(18, 52) * S
                    q = (mx + math.cos(a0) * L, my + math.sin(a0) * L)
                    cv.line((mx, my), q, 1.9 * S, c * 0.92, alpha=0.75, bow=r.normal(0, 0.12), dry=0.4, rag=3 * S)
                    if r.random() < 0.4:
                        a1 = a0 + r.uniform(-0.9, 0.9)
                        cv.line(q, (q[0] + math.cos(a1) * L * 0.6, q[1] + math.sin(a1) * L * 0.6), 1.4 * S, c * 0.9, alpha=0.6,
                                dry=0.5, rag=2 * S)

    # -------------------------------------------------------------- the plants
    def below(self, k_):
        """what a note has below ground: its seed and whatever roots it has put down."""
        cv, S, r = self.cv, self.S, self.r
        st = self.status[k_]
        x, y = self.seed_at(k_)
        root = lambda px_, py_: self.col((0.86, 0.80, 0.62), px_, py_, 0.85)           # noqa: E731
        depth = {"seed": 0.07, "growing": 0.30, "evergreen": 0.62}[st] * self.sd
        if st != "seed":                                                 # a tap root and its laterals
            tip = (x + r.normal(0, 14 * S), y + depth)
            tap = spline([(x, y), (x + r.normal(0, 9 * S), y + depth * 0.4), (x + r.normal(0, 12 * S), y + depth * 0.75), tip], 6)
            cv.stroke(tap, (6 if st == "evergreen" else 4) * S, root(x, y + depth / 2), dry=0.2, taper=(0.02, 0.6), rag=2 * S)
            for i in range(8 if st == "evergreen" else 5):
                t = r.uniform(0.12, 0.9)
                bx_, by_ = tap[int(t * (len(tap) - 1))]
                sg = r.choice([-1, 1])
                L = r.uniform(40, 120 if st == "evergreen" else 70) * S
                cv.stroke(bezier((bx_, by_), (bx_ + sg * L * 0.5, by_ + L * 0.1), (bx_ + sg * L, by_ + L * r.uniform(0.2, 0.6)), 7),
                          2.4 * S, root(bx_, by_), alpha=0.85, dry=0.3, taper=(0.02, 0.7), rag=2 * S)
        else:
            for sg in (-1, 1):                                           # the first root hairs
                L = r.uniform(18, 34) * S
                cv.stroke(bezier((x, y + 6 * S), (x + sg * L * 0.3, y + L * 0.7), (x + sg * L * 0.8, y + L), 6), 1.8 * S,
                          root(x, y), alpha=0.7, dry=0.4, taper=(0.02, 0.7), rag=2 * S)
        # the seed itself (or its split husk)
        husk = (0.66, 0.50, 0.28) if st == "seed" else (0.36, 0.27, 0.17)
        cv.dab(x, y, 23 * S, self.col(husk, x, y, 1.1), ang=-0.5, stretch=1.55, dry=0.05, jitter=0.05, thick=1.5)
        cv.dab(x - 3.5 * S, y - 4 * S, 7 * S, self.col(husk, x, y, 1.9) * 1.1, ang=-0.5, stretch=1.8, alpha=0.7)
        if st == "seed":                                                 # the radicle, just out
            cv.stroke(bezier((x + 3 * S, y + 5 * S), (x + 9 * S, y + 15 * S), (x + 1 * S, y + 21 * S), 6), 2.8 * S,
                      self.col((0.95, 0.93, 0.84), x, y, 0.9), dry=0.1, taper=(0.02, 0.5), rag=1)

    def above(self, k_, shadow=False):
        """what a note has above ground: its stake, and the plant if there is one.
        with shadow it is painted again, dark and shifted, as its shadow on the wall."""
        cv, S, r, H = self.cv, self.S, np.random.default_rng(sum(map(ord, k_)) + 5), self.H
        st = self.status[k_]
        x = self.px[k_]
        dx, dy = self.away(x, self.rt - H * 0.1, H * 0.022) if shadow else (0.0, 0.0)
        dark = self.col(WALL_N if self.night else WALL_D, x, self.rt - H * 0.08, 0.04) * 0.9

        def ink(alb, px_, py_, k=1.0):
            return dark if shadow else self.col(alb, px_, py_, k)
        kw = dict(alpha=0.6, dry=0.4) if shadow else dict(dry=0.15)
        # the stake stands beside the plant, a little off plumb
        sx = x + (0 if st == "seed" else 46 * S)
        lean = r.uniform(-9, 9) * S
        top = self.rt - H * (0.17 if self.view != "tall" else 0.13)
        cv.line((sx + dx, self.rt - 1 + dy), (sx + lean + dx, top + dy), 17 * S, ink(STAKE, sx, top + H * 0.07), jitter=0.05,
                rag=1.5 * S, taper=(0.02, 0.05), **kw)
        if not shadow:
            cv.line((sx + lean * 0.66, top + H * 0.055), (sx + lean, top), 17.5 * S, self.col(TAG, sx, top), dry=0.1, jitter=0.03,
                    rag=1.2 * S, taper=(0.02, 0.05))
            cv.line((sx, self.gt + 1), (sx, self.soil(sx) + 12 * S), 17 * S, self.col(STAKE, sx, self.gt, 0.4), dry=0.15,
                    rag=1.5 * S, taper=(0.02, 0.02))
            self.tag[k_] = (sx + lean, top)
        if st == "growing":
            g = (0.16, 0.50, 0.20)
            tip = (x + r.uniform(-14, 14) * S, self.rt - H * 0.12)
            stem = bezier((x, self.rt - 1), (x + r.uniform(-10, 10) * S, self.rt - H * 0.06), tip, 8) + [dx, dy]
            cv.stroke(stem, 6 * S, ink(g, x, tip[1]), taper=(0.02, 0.3), rag=1.5 * S, **kw)
            if not shadow:
                cv.line((x, self.gt + 1), (x, self.soil(x) + 4 * S), 6 * S, self.col(g, x, self.gt, 0.45), dry=0.15, rag=1.5 * S)
            mid = stem[3]
            for sg in (-1, 1):                                           # seed leaves, then true leaves
                a = (mid[0], mid[1])
                b = (mid[0] + sg * 38 * S, mid[1] - 10 * S)
                cv.stroke(bezier(a, ((a[0] + b[0]) / 2, a[1] - 16 * S), b, 7), 19 * S, ink(g, b[0], b[1], 1.0), taper=(0.5, 0.55),
                          rag=2 * S, jitter=0.07, **kw)
                a = (tip[0] + dx, tip[1] + dy)
                b = (a[0] + sg * 52 * S, a[1] - 34 * S)
                cv.stroke(bezier(a, (a[0] + sg * 14 * S, a[1] - 34 * S), b, 8), 23 * S, ink((0.20, 0.58, 0.24), b[0], b[1]),
                          taper=(0.5, 0.6), rag=2 * S, jitter=0.07, **kw)
                if not shadow:
                    cv.stroke(bezier(a, (a[0] + sg * 14 * S, a[1] - 34 * S), b, 8), 2.2 * S, self.col((0.5, 0.85, 0.45), b[0], b[1]),
                              alpha=0.7, dry=0.3, rag=2)
        elif st == "evergreen":
            tip = (x + r.uniform(-8, 8) * S, self.rt - H * (0.29 if self.view != "tall" else 0.24))
            tall_ = self.rt - tip[1]
            cv.line((x + dx, self.rt - 1 + dy), (tip[0] + dx, tip[1] + tall_ * 0.2 + dy), 10 * S, ink((0.30, 0.20, 0.12), x, tip[1]),
                    rag=1.5 * S, **kw)
            if not shadow:
                cv.line((x, self.gt + 1), (x, self.soil(x) + 4 * S), 10 * S, self.col((0.30, 0.20, 0.12), x, self.gt, 0.45), dry=0.15)
            levels = 8
            for i in range(levels):                                      # boughs, widest at the bottom
                t = i / (levels - 1)
                y = self.rt - tall_ * (0.10 + 0.84 * t)
                cx = x + (tip[0] - x) * (0.10 + 0.84 * t)
                bw = (150 - 122 * t) * S
                for sg in (-1, 1):
                    a = (cx + dx, y + dy)
                    b = (cx + sg * bw + dx, y + bw * 0.30 + dy)
                    green = (0.07, 0.29, 0.17) if (i + (sg > 0)) % 2 else (0.10, 0.36, 0.20)
                    cv.stroke(bezier(a, (cx + sg * bw * 0.5 + dx, y - bw * 0.10 + dy), b, 8), (26 - 15 * t) * S, ink(green, b[0], y),
                              taper=(0.15, 0.6), rag=5 * S, jitter=0.08, **kw)
                    if not shadow:
                        cv.stroke(bezier((a[0], a[1] - 3 * S), (cx + sg * bw * 0.5, y - bw * 0.16), (b[0], b[1] - 5 * S), 8), 3.4 * S,
                                  self.col((0.30, 0.62, 0.36), b[0], y, 1.2), alpha=0.6, dry=0.5, rag=4 * S)
            cv.line((tip[0] + dx, tip[1] + tall_ * 0.12 + dy), (tip[0] + dx, tip[1] + dy), 7 * S, ink((0.10, 0.36, 0.20), x, tip[1]),
                    taper=(0.02, 0.7), **kw)

    def glass(self):
        """the pane: the rail's shadow along its top, and the room caught in it."""
        cv, S, H, W = self.cv, self.S, self.H, self.W
        cv.line((self.ix0, self.gt + 5 * S), (self.ix1, self.gt + 5 * S), 12 * S, self.sc.tone(V(0.02, 0.022, 0.05)), alpha=0.5,
                glaze=True, soft=0.8, dry=0.2, rag=2)
        if self.view == "sprite":
            return
        for u, wdt, al in [(0.16, 70, 0.07), (0.21, 22, 0.09), (0.71, 46, 0.05)]:
            x0 = self.ix0 + (self.ix1 - self.ix0) * u
            cv.line((x0 + (self.gb - self.gt) * 0.5, self.gt + 8 * S), (x0, self.gb - 8 * S), wdt * S,
                    hexc("ffd08a") if self.night else hexc("ffffff"), alpha=al, glaze=True, soft=0.7, dry=0.25, jitter=0.02, rag=6 * S)
        if self.night:                                                   # the lamp, small, in the pane
            cv.dab(self.ix0 + W * 0.05, self.gt + H * 0.05, 26 * S, hexc("ffc45a"), stretch=1.0, alpha=0.20, glaze=True, soft=0.9)
            cv.dab(self.ix0 + W * 0.05, self.gt + H * 0.05, 8 * S, hexc("fff1cf"), stretch=1.0, alpha=0.55, glaze=True, soft=0.6)

    def lamp(self):
        """the same bare bulb as over the bench."""
        if self.view == "sprite":
            return
        cv, S, r = self.cv, self.S, self.r
        bx, by = self.bulb
        rr = 46 * S
        cord = hexc("05060d") if self.night else hexc("2a2a30")
        cv.stroke(bezier((bx + 5 * S, -30), (bx - 4 * S, by * 0.5), (bx, by - rr * 2.6), 8), 4.2 * S, cord, dry=0.1, jitter=0.02)
        if self.night:
            for k, (mul, al) in enumerate([(7.0, 0.05), (5.2, 0.07), (3.8, 0.10), (2.7, 0.15), (1.9, 0.24)]):
                for i in range(int(9 + mul * 2)):
                    a0 = r.uniform(0, 6.283)
                    cv.stroke(circle((bx, by), rr * mul * r.uniform(0.82, 1.0), a0, a0 + r.uniform(0.7, 1.3), 7), rr * mul * 0.55,
                              hexc("ffb347") if k < 3 else hexc("ffd58a"), alpha=al, glaze=True, soft=0.9, dry=0.2, jitter=0.02, rag=rr)
        hw = 52 * S
        hy = by - rr * 2.05
        cv.line((bx, hy - hw * 0.8), (bx, hy + hw * 0.75), hw, cord, dry=0.05, rag=1, taper=(0.02, 0.02))
        tones = [(1.12, "ff9d2e", 9), (0.96, "ffc45a", 8), (0.80, "ffe7ae", 7), (0.60, "fff6dc", 5), (0.36, "ffffff", 3)] if self.night \
            else [(1.0, "c9d2d6", 8), (0.75, "e6ecee", 6), (0.40, "f7fafb", 3)]
        for mul, c, n in tones:
            for i in range(n):
                a0 = 6.283 * i / n + r.uniform(-0.3, 0.3)
                d = rr * mul * 0.42
                cv.dab(bx + math.cos(a0) * d, by + rr * 0.08 + math.sin(a0) * d, rr * mul * 0.95, hexc(c), ang=a0 + 1.57,
                       stretch=1.25, dry=0.08, jitter=0.03, thick=1.7, soft=0.3)
        if self.night:                                                   # one moth, as ever
            mx, my, w, head = bx + rr * 3.4, by + rr * 0.9, 52 * S, 0.6
            hx, hy_ = math.cos(head), math.sin(head)
            for sg in (-1, 1):
                cv.dab(mx - hy_ * sg * w * 0.30 + hx * w * 0.05, my + hx * sg * w * 0.30 + hy_ * w * 0.05, w * 0.40, hexc("d9799c"),
                       ang=head + sg * 1.0, stretch=1.75, dry=0.3, jitter=0.08, thick=1.3)
            cv.line((mx - hx * w * 0.22, my - hy_ * w * 0.22), (mx + hx * w * 0.2, my + hy_ * w * 0.2), w * 0.13, hexc("8a8a3a"), dry=0.1)

    # ------------------------------------------------------------- the picture
    def paint(self, log=lambda *_: None):
        cv, t = self.cv, time.time()
        self.underdrawing()
        under = cv.render(relief=0)
        self.n_under = cv.n
        cv.paint_frame(int((46 if self.view != "sprite" else 22) * self.S))
        self.wall(False)
        self.wall(True)
        self.bench()
        self.frame()
        self.earth(False)
        self.block = cv.render()
        self.n_block = cv.n
        self.order_block = cv.order.copy()
        self.earth(True)
        self.stones()
        self.threads()
        for k_ in self.order:
            self.below(k_)
        for k_ in self.order:
            self.above(k_, shadow=True)
        for k_ in self.order:
            self.above(k_)
        # the rail again where things pass behind it, so they stand in the box and not on it
        cv.line((self.bx0, self.rt + 2 * self.S), (self.bx1, self.rt + 2 * self.S), 3 * self.S,
                self.col((0.80, 0.56, 0.34), self.W * 0.3, self.rt), alpha=0.8, dry=0.45)
        self.glass()
        self.lamp()
        self.final = cv.render()
        self.under = under
        log(f"  {self.mode}-{self.view}: {cv.n} strokes, {time.time() - t:.1f}s")
        return self.final

    def where(self):
        """where each stake and each thread ended up, 0..1, for the page."""
        W, H = self.W, self.H
        cw = min((self.ix1 - self.ix0) / len(self.order), W * 0.13)
        plants = {}
        for k_ in self.order:
            x = self.px[k_]
            tx, ty = self.tag[k_]
            y0, y1 = ty - H * 0.02, self.soil(x) + H * 0.10
            sx = x + (0 if self.status[k_] == "seed" else 46 * self.S)
            plants[k_] = {"box": [round(v, 4) for v in ((x - cw / 2) / W, y0 / H, cw / W, (y1 - y0) / H)],
                          "label": [round(sx / W, 4), round((self.rt + self.rh / 2) / H, 4)]}   # on the rail, under its stake
        threads = [{"a": a, "b": b, "d": [[round(px_ / W, 4), round(py_ / H, 4)] for px_, py_ in path[::2] + [path[-1]]]}
                   for a, b, path in self.thread_paths()]
        return {"order": self.order, "plants": plants, "threads": threads}


def export(job):
    mode, view, only = job
    b = Bed(mode, view, only=only)
    b.paint()
    if only:
        save(cv2.resize(b.final, VIEWS[view][3], interpolation=cv2.INTER_AREA), os.path.join(ROOT, "art", f"garden-{mode}-{only}.webp"), 80)
        return None
    meta = write_assets(b, os.path.join(ROOT, "art", f"garden-{mode}-{view}"), VIEWS[view][3])
    meta.update(b.where())
    return f"{mode}-{view}", meta


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opt = {sys.argv[i]: sys.argv[i + 1] for i in range(1, len(sys.argv) - 1) if sys.argv[i].startswith("--")}
    if args:
        b = Bed(args[0], args[1] if len(args) > 1 else "wide", float(opt.get("--scale", 1.0)), only=opt.get("--only"))
        b.paint(log=print)
        if "--preview" in opt:
            save(b.final, opt["--preview"])
        sys.exit(0)
    from multiprocessing import Pool
    os.makedirs(os.path.join(ROOT, "art"), exist_ok=True)
    jobs = [(m, v, None) for m in ("night", "day") for v in ("wide", "tall")]
    jobs += [(m, "sprite", s) for m in ("night", "day") for s in ("seed", "growing", "evergreen")]
    t = time.time()
    with Pool(min(6, os.cpu_count() or 1)) as pool:
        meta = dict(r for r in pool.map(export, jobs) if r)
    with open(os.path.join(ROOT, "art", "garden.js"), "w") as f:
        f.write("/* written by _tools/paint/garden.py. the planter, where its stakes and threads are, and how to replay it */\n")
        f.write("window.DSGARDEN=" + json.dumps(meta, separators=(",", ":")) + ";\n")
    for k, v in meta.items():
        print(f"  {k:11s} {v['strokes']} strokes")
    print(f"  painted in {time.time() - t:.0f}s")
