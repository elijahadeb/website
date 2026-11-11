#!/usr/bin/env python3
"""bench.py — the painting on the front page of deadsilicon.com.

    python3 _tools/paint/bench.py                 paint everything the site uses
    python3 _tools/paint/bench.py night wide      paint one picture (views: wide, tall, and the
                                                  close looks that head the inner pages:
                                                  planner, notebook, plant, screen)
    python3 _tools/paint/bench.py night wide --preview out.png --scale 0.5

the subject is the bench the engine gets written on, in lagos: the gtx 1050 era
dell, the keyboard, the phone on its gooseneck that films every session, the
raspberry pi, the meter in the wall socket, and a bare bulb. at night the bulb is
the light and the moths come. by day the sun comes through the burglar bars.

the brief the painter works to — one hand, so the pictures agree with each other:
  - planes first. every surface is one colour decision, laid with a flat brush in
    the direction the surface runs. detail goes on last and there is little of it.
  - colour only shows where there is light. shadows are not black, they are the
    colour of the room without the lamp.
  - shadows are real: something stands between the spot and the lamp.
  - the picture stops where the paint stops. the pencil underneath is left in.

nothing is traced and there is no image model. the room is described in metres,
the light is worked out for each stroke, and every stroke is placed by engine.py.
"""
import math
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Canvas, Mask, bezier, spline, hexc, smooth, F          # noqa: E402
from world import Cam, Box, Lamp, Scene, V, unit, rot_x, rot_y            # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GROUND = {"night": "10142a", "day": "dde4dc"}   # the toned ground, and the page colour of the site
# every way the bench gets looked at. name: canvas w, h, where the eye is, what it looks at,
# field of view, brush scale, and the size the picture is saved at.
VIEWS = {
    "wide": (2400, 1200, V(0.10, 1.50, 2.25), V(0.02, 0.985, 0.25), 46, 1.0, (2000, 1000)),
    "tall": (1500, 1800, V(0.05, 1.50, 2.00), V(-0.04, 1.075, 0.25), 37, 0.9, (1000, 1200)),
    # close looks at one thing each. these head the inner pages: you clicked the planner
    # in the painting, and the log opens under the planner.
    "planner": (2100, 700, V(0.56, 1.12, 1.62), V(0.60, 1.065, 0.0), 40, 1.0, (1500, 500)),
    "notebook": (2100, 700, V(-0.20, 1.20, 1.18), V(-0.36, 0.80, 0.50), 40, 1.0, (1500, 500)),
    "plant": (2100, 700, V(-0.50, 1.08, 1.45), V(-0.64, 0.955, 0.05), 40, 1.0, (1500, 500)),
    "screen": (2100, 700, V(0.03, 1.00, 1.45), V(-0.03, 0.885, 0.26), 40, 1.0, (1500, 500)),
}
DESK = 0.75                                   # height of the desk top, metres
BULB = V(-0.16, 1.255, 0.38)
WIN = (-0.93, -0.43, 0.965, 1.66)              # window opening on the wall: x0, x1, y0, y1


class Painter:
    def __init__(self, mode="night", view="wide", scale=1.0):
        self.mode, self.view = mode, view
        self.night = mode == "night"
        W, H, pos, look, fov, k = VIEWS[view][:6]
        self.S = S = scale * k
        W, H = int(W * scale), int(H * scale)
        self.W, self.H = W, H
        cam = (pos, look, fov)
        self.cam = Cam(cam[0], cam[1], cam[2], W, H)
        self.ground = hexc(GROUND[mode])
        self.pencil = hexc("7f8bb8") if self.night else hexc("5b5f6e")
        self.cv = Canvas(W, H, self.ground, seed=7)
        self.r = self.cv.rng
        self.sc = Scene()
        self.build()
        self.light()

    # ------------------------------------------------------------------ the room
    def build(self):
        sc = self.sc
        lap_yaw = math.radians(-9)
        self.lap = sc.add(Box((-0.03, DESK + 0.009, 0.335), (0.357, 0.018, 0.235), yaw=lap_yaw))
        tilt = math.radians(17)
        hinge = self.lap.at(0, 1, -1)
        R = rot_y(lap_yaw) @ rot_x(-tilt)
        self.scr = sc.add(Box(hinge + R @ V(0, 0.1125, 0), (0.357, 0.225, 0.007), R=R))
        self.kbd = sc.add(Box((0.04, DESK + 0.014, 0.575), (0.325, 0.028, 0.125), yaw=math.radians(5)))
        self.book = sc.add(Box((-0.40, DESK + 0.006, 0.53), (0.150, 0.012, 0.205), yaw=math.radians(-24)))
        self.pi = sc.add(Box((-0.47, DESK + 0.014, 0.30), (0.085, 0.004, 0.056), yaw=math.radians(24)))
        self.meter = sc.add(Box((0.275, 1.075, 0.032), (0.066, 0.122, 0.064)))
        self.brick = sc.add(Box((0.34, DESK + 0.014, 0.20), (0.105, 0.028, 0.048), yaw=math.radians(28)))
        self.rigbase = sc.add(Box((0.60, DESK + 0.018, 0.33), (0.115, 0.036, 0.095), yaw=math.radians(-14)))
        self.stem = sc.add(Box((0.60, DESK + 0.036 + 0.085, 0.33), (0.034, 0.17, 0.034)))
        # the gooseneck: up out of the stem, once round a loop, then over toward the keys
        top = V(0.60, DESK + 0.206, 0.33)
        loop = [top + V(0, 0.02, 0)]
        for i in range(1, 12):
            a = -math.pi / 2 + i / 11 * math.pi * 2.0
            loop.append(top + V(0.105 * math.cos(a), 0.13 + 0.105 * math.sin(a), 0.03 * math.sin(a * 0.5)))
        self.neck_pts = loop + [top + V(-0.06, 0.10, 0.06), top + V(-0.14, 0.160, 0.13), top + V(-0.21, 0.165, 0.185)]
        self.phone_c = top + V(-0.255, 0.155, 0.215)
        Rp = rot_y(math.radians(24)) @ rot_x(math.radians(-48))
        self.phone = sc.add(Box(self.phone_c, (0.076, 0.162, 0.009), R=Rp))
        s3 = spline3(self.neck_pts, 5)
        self.neck = s3
        for q in s3[::2]:
            sc.add(Box(q, (0.017, 0.017, 0.017)))
        self.tin = sc.add(Box((-0.705, DESK + 0.047, 0.145), (0.078, 0.094, 0.078), yaw=math.radians(18)))
        # the bulb's own holder, so it shades the ceiling side
        self.holder = Box(BULB + V(0, 0.062, 0), (0.036, 0.05, 0.036), shadow=False)

    def light(self):
        sc = self.sc
        if self.night:
            sc.amb_up, sc.amb_dn = V(0.050, 0.105, 0.290), V(0.035, 0.055, 0.150)
            sc.haze = V(0.035, 0.050, 0.115)
            sc.exposure = 1.45
            sc.chroma = 1.38
            sc.lamps.append(Lamp(BULB, V(1.00, 0.76, 0.44) * 0.50, radius=0.028))
            n = self.scr.R[:, 2]
            sc.lamps.append(Lamp(self.scr.at(0, 0, 1) + n * 0.02, V(0.55, 0.72, 1.0) * 0.10, shadow=False,
                                 facing=n, wrap=0.1))
        else:
            sc.amb_up, sc.amb_dn = V(0.52, 0.63, 0.80), V(0.60, 0.52, 0.40)
            # the window itself is a lamp by day: cool, wide, from the left, so things have a lit side
            sc.lamps.append(Lamp(V(-0.68, 1.28, 0.12), V(0.80, 0.92, 1.0) * 0.33, radius=0.13, wrap=0.6))
            sc.haze = V(0.03, 0.04, 0.07)
            sc.exposure = 1.6
            sc.chroma = 1.45
            sd = unit(V(0.50, -0.56, 0.66))
            sc.sun = (sd, V(2.5, 1.95, 1.15), self.sun_gate)

    def sun_gate(self, x, y):
        """what the window lets through: the opening, minus the frame and the bars."""
        x0, x1, y0, y1 = WIN
        if not (x0 < x < x1 and y0 < y < y1):
            return 0.0
        mid = (x0 + x1) / 2
        if abs(x - mid) < 0.022 or x - x0 < 0.03 or x1 - x < 0.03 or y - y0 < 0.03:
            return 0.0
        for bx in self.bars():
            if abs(x - bx) < 0.007:
                return 0.0
        if abs(((y - y0) % 0.22) - 0.11) < 0.006:
            return 0.0
        return 1.0

    def bars(self):
        x0, x1, _, _ = WIN
        n = 6
        return [x0 + (x1 - x0) * (i + 0.5) / n for i in range(n)]

    # ------------------------------------------------------------------- helpers
    def P(self, p):
        return self.cam.p(p)

    def px(self, p, m):
        return self.cam.px(p, m)

    def plane_fill(self, quad, N, albedo, dir3, w, l, gloss=0.0, emit=None, samples=4, bounds=None, **kw):
        """lay strokes over a flat surface. each stroke asks the room for its own light."""
        cam, sc, S = self.cam, self.sc, self.S
        P0 = quad[0]
        poly = bounds if bounds is not None else [cam.p(q) for q in quad]

        def col(x, y):
            Pw = cam.on_plane(x, y, P0, N)
            if Pw is None:
                return self.ground
            a = albedo(Pw) if callable(albedo) else albedo
            e = emit(Pw) if callable(emit) else emit
            return sc.shade(Pw, N, a, samples, gloss, cam.pos, e)

        def ang(x, y):
            Pw = cam.on_plane(x, y, P0, N)
            if Pw is None:
                return 0.0
            d = dir3(Pw) if callable(dir3) else dir3
            a, b = cam.p(Pw), cam.p(Pw + d * 0.02)
            return math.atan2(b[1] - a[1], b[0] - a[0])

        self.cv.fill(poly, col, ang, w * S, l * S, **kw)

    def box(self, b, albedo, w=12, l=44, faces=None, dirs=None, **kw):
        for name, q, n in b.visible(self.cam):
            if faces and name not in faces:
                continue
            a = albedo[name] if isinstance(albedo, dict) else albedo
            if a is None:
                continue
            d = (dirs or {}).get(name)
            if d is None:
                d = b.R[:, 0] if name[1] != "x" else b.R[:, 2]
            kw.setdefault("density", 1.35)
            self.plane_fill(q, n, a, d, w, l, **kw)

    def tube(self, pts3, radius, dark, lit=None, n=6, **kw):
        cam = self.cam
        p2 = spline([cam.p(q) for q in pts3], n) if len(pts3) > 2 else np.array([cam.p(q) for q in pts3], F)
        mid = pts3[len(pts3) // 2]
        w = max(1.6 * self.S, cam.px(mid, radius * 2))
        self.cv.stroke(p2, w, dark, dry=0.08, jitter=0.03, rag=w * 0.2, **kw)
        if lit is not None:
            self.cv.stroke(p2 + np.array([-w * 0.16, -w * 0.20], F), max(1.0, w * 0.32), lit, dry=0.25,
                           jitter=0.03, alpha=0.9, rag=w * 0.5)

    def sketch(self, a, b, over=0.05, alpha=0.8):
        a, b = np.asarray(a, F), np.asarray(b, F)
        d = b - a
        self.cv.line(a - d * over, b + d * over, 2.1 * self.S, self.pencil, bow=self.r.normal(0, 0.006),
                     alpha=alpha, dry=0.4, scumble=0.22, jitter=0, nb=2, free=True, glaze=True, soft=0.5, rag=3)

    def sketch_box(self, b, **kw):
        c = [self.P(b.at(*s)) for s in [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
                                         (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]]
        for i, j in [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]:
            self.sketch(c[i], c[j], **kw)

    def lit(self, P, N, albedo, **kw):
        return self.sc.shade(P, N, albedo, view=self.cam.pos, **kw)

    def clipped(self, quad):
        """a surface's outline on the canvas, cut to the canvas."""
        return clip_poly([self.P(q) for q in quad], -40, -40, self.W + 40, self.H + 40)

    # -------------------------------------------------------------- underdrawing
    def underdrawing(self):
        cv, P = self.cv, self.P
        W, H = self.W, self.H
        # where the desk meets the wall, and the desk's front edge
        self.sketch(P(V(-1.6, DESK, 0)), P(V(1.6, DESK, 0)), over=0)
        for z in (0.26, 0.52, 0.78):
            self.sketch(P(V(-1.3, DESK, z)), P(V(1.3, DESK, z)), over=0, alpha=0.3)
        x0, x1, y0, y1 = WIN
        for a, b in [((x0, y0), (x1, y0)), ((x0, y0), (x0, y1)), ((x1, y0), (x1, y1)),
                     (((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1))]:
            self.sketch(P(V(a[0], a[1], 0)), P(V(b[0], b[1], 0)))
        for b in (self.lap, self.scr, self.kbd, self.book, self.meter, self.rigbase, self.stem, self.phone, self.brick, self.tin):
            self.sketch_box(b)
        n2 = spline([P(q) for q in self.neck_pts], 6)
        cv.stroke(n2, 1.7 * self.S, self.pencil, alpha=0.5, scumble=0.2, nb=2, free=True, glaze=True, jitter=0)
        # the cord, the bulb, and a plumb line through it
        bp = P(BULB)
        self.sketch((bp[0], -10), (bp[0], bp[1]), over=0)
        rr = self.px(BULB, 0.032)
        cv.stroke(circle(bp, rr), 1.7 * self.S, self.pencil, alpha=0.5, scumble=0.2, nb=2, free=True, glaze=True, jitter=0)
        cv.stroke(circle(bp, rr * 5.5, 0.3, 5.2), 1.5 * self.S, self.pencil, alpha=0.28, scumble=0.3, nb=2, free=True,
                  glaze=True, jitter=0)
        # a horizon and a centre line, the way a picture gets squared up
        self.sketch((W * 0.02, H * 0.5), (W * 0.98, H * 0.5), over=0, alpha=0.16)
        self.sketch((W * 0.5, H * 0.03), (W * 0.5, H * 0.97), over=0, alpha=0.16)

    # ---------------------------------------------------------------------- wall
    def wall_albedo(self, Pw):
        x, y = Pw[0], Pw[1]
        base = V(0.70, 0.76, 0.66) if self.night else V(0.50, 0.74, 0.66)   # washed mint distemper
        damp = 0.5 + 0.5 * math.sin(x * 3.1 + 1.3 * math.sin(y * 4.0)) * math.sin(y * 2.3 + x)
        base = base * (0.86 + 0.14 * damp)
        grime = smooth(0.30, 0.0, y - DESK)                        # hands and years, just above the desk
        return base * (1 - 0.22 * grime) + V(0.10, 0.06, 0.0) * grime * 0.25

    def wall(self, fine=False):
        cam, S = self.cam, self.S
        quad = [V(-1.7, 1.95, 0), V(1.7, 1.95, 0), V(1.7, DESK - 0.01, 0), V(-1.7, DESK - 0.01, 0)]
        bp = np.array(self.P(V(BULB[0], BULB[1], 0)))
        rad = self.px(V(BULB[0], BULB[1], 0), 0.55)

        def ang(x, y):                       # the strokes ring the lamp, and settle to a slant away from it
            dx, dy = x - bp[0], y - bp[1]
            d = math.hypot(dx, dy) / rad
            ring = math.atan2(dy, dx) + math.pi / 2
            k = float(smooth(1.5, 0.35, d)) if self.night else 0.0
            flat = -0.42 + 0.25 * math.sin(x / (300 * S))
            return math.atan2(k * math.sin(ring) + (1 - k) * math.sin(flat), k * math.cos(ring) + (1 - k) * math.cos(flat))

        P0, N = quad[0], V(0, 0, 1)

        def col(x, y):
            Pw = cam.on_plane(x, y, P0, N)
            return self.sc.shade(Pw, N, self.wall_albedo(Pw), 4 if fine else 3)

        poly = self.clipped(quad)
        if not fine:
            self.cv.fill(poly, col, ang, 54 * S, 175 * S, density=1.35, clip=True, dry=0.14, coljit=0.035, feather=0)
        else:
            self.cv.fill(poly, col, ang, 30 * S, 96 * S, density=0.62, clip=True, dry=0.36, coljit=0.05, feather=0,
                         pickup=0.3)

    # -------------------------------------------------------------------- window
    def window(self, fine=False):
        cv, S, r, P = self.cv, self.S, self.r, self.P
        x0, x1, y0, y1 = WIN
        y1v = 1.72
        q = [V(x0, y1v, 0), V(x1, y1v, 0), V(x1, y0, 0), V(x0, y0, 0)]
        poly = [P(p) for p in q]
        mk = Mask(poly, self.W, self.H, feather=0.7)
        top, bot = P(V(x0, y1v, 0))[1], P(V(x0, y0, 0))[1]
        lft, rgt = P(V(x0, y0, 0))[0], P(V(x1, y0, 0))[0]
        if not fine:
            if self.night:
                def sky(x, y):
                    t = (y - top) / (bot - top)
                    c = hexc("0b1030") * (1 - t) + hexc("3a2f55") * t      # the city glows from below
                    return c + hexc("6b3a2a") * float(smooth(0.72, 1.0, t)) * 0.55
            else:
                def sky(x, y):
                    t = (y - top) / (bot - top)
                    return hexc("9cc3e6") * (1 - t) + hexc("f1e7cf") * t   # harmattan: the sky bleaches low down
            cv.fill(poly, sky, 0.04, 26 * S, 110 * S, density=1.2, clip=True, dry=0.25, coljit=0.025)
            # the neighbours: roofs, a water tank on its stand, a mast
            base = bot - (bot - top) * (0.30 if self.night else 0.20)
            roofs = [(0.00, 0.26, 0.10), (0.20, 0.50, 0.19), (0.44, 0.74, 0.07), (0.66, 1.00, 0.15)]
            if not self.night:
                roofs = [(0.00, 0.30, 0.05), (0.24, 0.52, 0.10), (0.46, 0.76, 0.03), (0.70, 1.00, 0.07)]
                for a, b, hgt in [(0.05, 0.40, 0.17), (0.50, 0.95, 0.14)]:          # blocks further off, in the haze
                    xa, xb = lft + (rgt - lft) * a, lft + (rgt - lft) * b
                    cv.fill([(xa, base - (bot - top) * hgt), (xb, base - (bot - top) * hgt), (xb, base), (xa, base)],
                            hexc("c9d2d2"), 1.57, 12 * S, 40 * S, clip=True, dry=0.3, coljit=0.03)
            for a, b, hgt in roofs:
                xa, xb = lft + (rgt - lft) * a, lft + (rgt - lft) * b
                yt = base - (bot - top) * hgt
                if self.night:
                    c = hexc("0d1126") * r.uniform(0.9, 1.25)
                else:
                    c = (hexc("9c5a44") if r.random() < 0.5 else hexc("a9adb0")) * r.uniform(0.85, 1.1)
                cv.fill([(xa, yt), (xb, yt - (bot - top) * 0.025), (xb, bot), (xa, bot)], c, 0.5 if self.night else 1.45,
                        14 * S, 46 * S, clip=True, dry=0.2, coljit=0.05)
                if not self.night:                                     # the sunny pitch of the roof
                    cv.fill([(xa, yt), (xb, yt - (bot - top) * 0.025), (xb, yt + (bot - top) * 0.07), (xa, yt + (bot - top) * 0.09)],
                            c * 1.25 + 0.06, 1.45, 9 * S, 30 * S, clip=True, dry=0.3, coljit=0.05)
            tx = lft + (rgt - lft) * 0.34
            ty = base - (bot - top) * 0.19
            tw, th = (rgt - lft) * 0.085, (bot - top) * 0.13
            tank = hexc("080a18") if self.night else hexc("1d2026")
            for lx in (-0.8, 0.8):                                     # the stand
                cv.line((tx + lx * tw, ty), (tx + lx * tw * 1.15, ty + th * 1.3), 4 * S, tank, clip=mk, dry=0.1)
            cv.fill([(tx - tw, ty - th), (tx + tw, ty - th), (tx + tw, ty), (tx - tw, ty)], tank, 1.57, 8 * S, 30 * S,
                    clip=True, dry=0.15)
            if not self.night:
                cv.line((tx - tw * 0.55, ty - th * 0.9), (tx - tw * 0.55, ty - th * 0.1), 4 * S, hexc("4a5058"), dry=0.4, clip=mk)
            mx = lft + (rgt - lft) * 0.83
            cv.line((mx, base - (bot - top) * 0.15), (mx, top + (bot - top) * 0.20), 3.2 * S,
                    hexc("161a34") if self.night else hexc("7c8088"), clip=mk, dry=0.2)
            for i in range(4):
                yy = top + (bot - top) * (0.24 + i * 0.09)
                cv.line((mx - 9 * S, yy), (mx + 9 * S, yy + 3 * S), 2.2 * S,
                        hexc("161a34") if self.night else hexc("7c8088"), clip=mk)
            if self.night:
                cv.dab(mx, top + (bot - top) * 0.20, 7 * S, hexc("ff4a2a"), clip=mk)
                for i in range(46):                                    # other people's lamps
                    x = r.uniform(lft, rgt)
                    y = r.uniform(base - (bot - top) * 0.16, bot - (bot - top) * 0.03)
                    c = [hexc("ffc26a"), hexc("ffd9a0"), hexc("9fd0ff"), hexc("ff9a4a")][int(r.integers(0, 4))]
                    cv.dab(x, y, r.uniform(3, 7) * S, c * r.uniform(0.55, 1.0), ang=0.0, clip=mk, dry=0.2)
                for i in range(14):                                    # a few stars the city leaves
                    cv.dab(r.uniform(lft, rgt), r.uniform(top, top + (bot - top) * 0.45), r.uniform(2, 3.4) * S,
                           hexc("c9d3ff") * r.uniform(0.5, 0.95), clip=mk)
            else:
                # a pawpaw tree and the wires everyone's light comes down
                px_ = lft + (rgt - lft) * 0.60
                cv.line((px_, base), (px_ + 6 * S, base - (bot - top) * 0.30), 5 * S, hexc("6a5a44"), clip=mk)
                for i in range(9):
                    a = -math.pi * i / 8
                    cx_, cy_ = px_ + 6 * S, base - (bot - top) * 0.30
                    cv.line((cx_, cy_), (cx_ + math.cos(a) * 46 * S, cy_ + math.sin(a) * 30 * S - 6 * S), 9 * S,
                            hexc("3f7a45") * r.uniform(0.8, 1.2), clip=mk, dry=0.35)
                for k in range(3):
                    yy = top + (bot - top) * (0.40 + k * 0.035)
                    cv.line((lft, yy), (rgt, yy + (bot - top) * 0.05), 1.6 * S, hexc("3a3d48"), bow=0.03, clip=mk, alpha=0.8)
            return
        # glass louvres: each blade catches a line of light along its lower edge
        nb = 7
        for i in range(nb + 1):
            y = y0 + (y1v - y0) * i / nb
            a, b = P(V(x0, y, 0)), P(V(x1, y, 0))
            edge = hexc("5c6fa8") if self.night else hexc("f6fbff")
            cv.line(a, b, 2.4 * S, edge, alpha=0.55 if self.night else 0.75, clip=mk, dry=0.45, jitter=0.02)
            if i < nb:
                a2, b2 = P(V(x0, y + 0.03, 0)), P(V(x1, y + 0.03, 0))
                cv.line(a2, b2, 13 * S, hexc("8fa3d8") if self.night else hexc("ffffff"), alpha=0.07 if self.night else 0.16,
                        clip=mk, glaze=True, dry=0.3)
        if self.night:                                                 # the bulb, seen again in two of the blades
            for i in (1, 2):
                y = y0 + (y1v - y0) * (i + 0.45) / nb
                a = P(V(x1 - 0.13, y, 0))
                cv.dab(a[0], a[1], 9 * S, hexc("ffb45a"), ang=0.0, stretch=3.4, alpha=0.75, clip=mk)
        # burglar bars, then the frame over everything
        bar = hexc("0a0c1a") if self.night else hexc("2c2a2b")
        for bx in self.bars():
            a, b = P(V(bx, y0, 0.012)), P(V(bx, y1v, 0.012))
            cv.line(a, b, max(2.2 * S, self.px(V(bx, 1.3, 0), 0.012)), bar, dry=0.12, jitter=0.03)
            if self.night:
                cv.line((a[0] + 2.6 * S, a[1]), (b[0] + 2.6 * S, b[1]), 1.6 * S, hexc("c98b4a"), alpha=0.55, dry=0.5)
        for yb in (y0 + 0.11, y0 + 0.33, y0 + 0.55):
            a, b = P(V(x0, yb, 0.012)), P(V(x1, yb, 0.012))
            cv.line(a, b, 2.6 * S, bar, dry=0.12)
        fr = V(0.80, 0.80, 0.74)
        t = 0.032
        parts = [(x0 - t, x0, y0 - t, y1v), (x1, x1 + t, y0 - t, y1v), ((x0 + x1) / 2 - 0.02, (x0 + x1) / 2 + 0.02, y0, y1v),
                 (x0 - t, x1 + t, y0 - t, y0)]
        for a, b, c, d in parts:
            qq = [V(a, d, 0.02), V(b, d, 0.02), V(b, c, 0.02), V(a, c, 0.02)]
            vert = (b - a) < (d - c)
            self.plane_fill(qq, V(0, 0, 1), fr, V(0, 1, 0) if vert else V(1, 0, 0), 9, 46, dry=0.25, coljit=0.04)
        sill = Box(((x0 + x1) / 2, y0 - t - 0.010, 0.022), (x1 - x0 + 0.10, 0.020, 0.044))
        self.box(sill, fr * 1.05, w=9, l=50, dry=0.2)

    # ---------------------------------------------------------------------- desk
    def desk_albedo(self, Pw):
        plank = int(math.floor(Pw[2] / 0.128))
        k = [1.0, 0.86, 1.08, 0.92, 1.02, 0.88, 1.05][plank % 7]
        streak = 0.94 + 0.06 * math.sin(Pw[0] * 37 + plank * 2.1) * math.sin(Pw[0] * 9.0 + plank)
        return V(0.46, 0.285, 0.165) * k * streak

    def desk(self, fine=False):
        S = self.S
        quad = [V(-1.9, DESK, 0.0), V(1.9, DESK, 0.0), V(1.9, DESK, 1.5), V(-1.9, DESK, 1.5)]
        N = V(0, 1, 0)
        poly = self.clipped(quad)
        if not fine:
            self.plane_fill(quad, N, self.desk_albedo, V(1, 0, 0), 36, 180, gloss=0.5, bounds=poly, density=1.35,
                            dry=0.14, coljit=0.035, angjit=0.035, feather=0)
        else:
            fl, fd = (17, 0.8) if self.night else (13, 1.05)        # by day the bars' shadows want shorter strokes
            self.plane_fill(quad, N, self.desk_albedo, V(1, 0, 0), fl, 66 if self.night else 38, gloss=0.9, bounds=poly, density=fd,
                            dry=0.4, coljit=0.05, angjit=0.03, feather=0, samples=5, pickup=0.2)
            for i in range(1, 9):                                      # the joins between the planks
                z = i * 0.128
                a, b = self.P(V(-1.5, DESK, z)), self.P(V(1.5, DESK, z))
                self.cv.line(a, b, 2.2 * S, self.lit(V(0, DESK, z), N, V(0.10, 0.06, 0.04)), alpha=0.7, dry=0.5, scumble=0.2)
            a, b = self.P(V(-1.6, DESK + 0.002, 0.004)), self.P(V(1.6, DESK + 0.002, 0.004))
            self.cv.line(a, b, 4 * S, self.sc.tone(V(0.02, 0.022, 0.05)), alpha=0.8, dry=0.3)

    # -------------------------------------------------------------------- laptop
    def laptop(self, fine=False):
        cv, S, lap, scr, P = self.cv, self.S, self.lap, self.scr, self.P
        carbon, alu = V(0.085, 0.088, 0.10), V(0.62, 0.63, 0.66)
        top = lambda u, v, lift=0.0: lap.at(u * 2 - 1, 1 + lift / lap.h[1], v * 2 - 1)   # noqa: E731
        N = lap.R[:, 1]
        if not fine:
            self.box(lap, {"+y": carbon, "+z": alu, "-x": alu, "+x": alu, "-z": alu, "-y": None}, w=10, l=60, dry=0.2, gloss=0.3)
            # the lid: bezel, then the lit panel
            q, n = scr.face("+z")
            self.plane_fill(q, n, V(0.02, 0.02, 0.025), scr.R[:, 0], 12, 70, dry=0.15)
            for name in ("+y", "-x", "+x"):
                qq, nn = scr.face(name)
                if float((self.cam.pos - sum(qq) / 4) @ nn) > 0:
                    self.plane_fill(qq, nn, alu, scr.R[:, 0] if name == "+y" else scr.R[:, 1], 4, 40, dry=0.2)
            self.panel(False)
            return
        # the keyboard well, the keys, the touchpad
        well = [top(0.075, 0.07), top(0.925, 0.07), top(0.925, 0.60), top(0.075, 0.60)]
        self.plane_fill(well, N, V(0.03, 0.03, 0.036), lap.R[:, 0], 7, 40, dry=0.2)
        rows = [14, 14, 14, 13, 12, 9]
        for j, n in enumerate(rows):
            v0 = 0.085 + j * 0.0845
            for i in range(n):
                u0 = 0.09 + i * (0.82 / n)
                u1 = u0 + (0.82 / n) * 0.80
                if j == 5 and i in (3, 4, 5):                          # the space bar
                    if i != 3:
                        continue
                    u1 = u0 + (0.82 / n) * 2.85
                c = top((u0 + u1) / 2, v0 + 0.035, 0.001)
                col = self.lit(c, N, V(0.075, 0.078, 0.09), samples=3, gloss=0.25)
                a, b = P(top(u0, v0 + 0.034, 0.001)), P(top(u1, v0 + 0.034, 0.001))
                cv.line(a, b, max(2.0, self.px(c, 0.0125)), col, dry=0.12, jitter=0.05, rag=1.2, soft=0.25, taper=(0.02, 0.02))
        pad = [top(0.355, 0.66), top(0.645, 0.66), top(0.645, 0.955), top(0.355, 0.955)]
        self.plane_fill(pad, N, V(0.20, 0.205, 0.22), lap.R[:, 0], 7, 46, dry=0.2, gloss=0.6, coljit=0.03)
        # the carbon weave: short strokes one way, then the other
        for k in range(150):
            u, v = self.r.uniform(0.03, 0.97), self.r.uniform(0.63, 0.97)
            if 0.34 < u < 0.66 and v > 0.64:
                continue
            c = top(u, v, 0.0006)
            col = self.lit(c, N, V(0.16, 0.165, 0.185), samples=2)
            d = (0.022, 0.022) if k % 2 else (0.022, -0.022)
            cv.line(P(top(u - d[0], v - d[1], 0.0006)), P(top(u + d[0], v + d[1], 0.0006)), 2.4 * S, col, alpha=0.55, dry=0.5, scumble=0.2)
        # the front lip catches the lamp
        a, b = P(lap.at(-1, 1, 1)), P(lap.at(1, 1, 1))
        cv.line(a, b, 2.6 * S, self.lit(lap.at(0, 1, 1), N, V(0.9, 0.9, 0.92), gloss=0.5), dry=0.35, alpha=0.9)
        self.panel(True)
        a, b = P(scr.at(-1, 1, 1)), P(scr.at(1, 1, 1))
        cv.line(a, b, 2.2 * S, self.lit(scr.at(0, 1, 0), scr.R[:, 1], V(0.9, 0.9, 0.92)), dry=0.35, alpha=0.85)

    def panel(self, fine):
        """the screen. a terminal: what ran, what it printed, a cursor waiting."""
        cv, S, scr, r, P = self.cv, self.S, self.scr, self.r, self.P
        g = lambda u, v: scr.at(u * 2 - 1, 1 - v * 2, 1.02)             # noqa: E731  u right, v down
        k = 1.0 if self.night else 0.55
        if not fine:
            poly = [P(g(0.03, 0.045)), P(g(0.97, 0.045)), P(g(0.97, 0.93)), P(g(0.03, 0.93))]
            cx, cy = P(g(0.5, 0.5))

            def col(x, y):
                d = math.hypot(x - cx, (y - cy) * 1.4) / (300 * S)
                return (hexc("16233f") * (1 - 0.35 * d) + hexc("0b1226") * 0.35 * d) * (k * 0.9 + 0.1)
            a = P(g(0, 0.5))
            b = P(g(1, 0.5))
            cv.fill(poly, col, math.atan2(b[1] - a[1], b[0] - a[0]), 15 * S, 80 * S, density=1.2, dry=0.15, coljit=0.03)
            return
        ink = {"dim": hexc("5d78a6"), "txt": hexc("c9dcf5"), "ok": hexc("8fe0a4"), "num": hexc("ffc66a"), "bad": hexc("ff7a5c")}
        lines = [("dim", [5, 9, 4]), ("txt", [3, 11, 6, 4]), ("txt", [7, 5]), ("ok", [2]), ("dim", []),
                 ("dim", [5, 12]), ("txt", [4, 4, 9]), ("num", [6, 3]), ("txt", [4, 4, 9]), ("num", [6, 3]),
                 ("txt", [4, 4, 9]), ("num", [7, 3]), ("bad", [3, 8, 5]), ("dim", []), ("txt", [2, 6])]
        w = max(1.8, self.px(scr.c, 0.0052))
        for j, (kind, words) in enumerate(lines):
            v = 0.095 + j * 0.054
            u = 0.065 + (0.03 if kind == "num" else 0)
            for n in words:
                u1 = u + n * 0.0165
                cv.line(P(g(u, v)), P(g(u1, v)), w, ink[kind] * r.uniform(0.82, 1.0) * k, dry=0.2, jitter=0.04,
                        rag=1.5, soft=0.3, taper=(0.02, 0.02))
                u = u1 + 0.02
        v = 0.095 + (len(lines) - 1) * 0.054
        cv.line(P(g(0.235, v)), P(g(0.262, v)), w * 2.0, hexc("ffb347") * k, dry=0.05, rag=0.5, taper=(0.02, 0.02))
        # the room in the glass: a smear of the lamp
        if self.night:
            a, b = P(g(0.58, 0.10)), P(g(0.80, 0.30))
            cv.line(a, b, 26 * S, hexc("ffb45a"), alpha=0.07, glaze=True, dry=0.2)

    # ------------------------------------------------------------- the other keys
    def keyboard(self, fine=False):
        cv, S, kb, P = self.cv, self.S, self.kbd, self.P
        N = kb.R[:, 1]
        case = V(0.07, 0.07, 0.08)
        if not fine:
            self.box(kb, case, w=11, l=60, dry=0.2, gloss=0.05)
            return
        top = lambda u, v, lift=0.0: kb.at(u * 2 - 1, 1 + lift / kb.h[1], v * 2 - 1)     # noqa: E731
        rows = [(15, 0), (15, 0), (14, 0.02), (13, 0.035), (11, 0.0)]
        for j, (n, off) in enumerate(rows):
            v0 = 0.075 + j * 0.178
            v1 = v0 + 0.150
            ucur = 0.03 + off
            widths = [1.0] * n
            if j == 4:
                widths = [1.25, 1.25, 1.25, 6.2, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
            elif j == 1:
                widths[-1] = 1.9
            elif j == 2:
                widths[0], widths[-1] = 1.5, 1.4
            elif j == 3:
                widths[0], widths[-1] = 2.1, 2.1
            unit_w = (0.94 - off) / sum(widths) if j else 0.94 / 16.2
            for i, wd in enumerate(widths):
                u0, u1 = ucur, ucur + unit_w * wd
                ucur = u1
                if j == 0 and i == n - 1:                              # the knob, top right
                    c = top(0.955, v0 + 0.07, 0.012)
                    rr = self.px(c, 0.0105)
                    pc = P(c)
                    cv.dab(pc[0], pc[1], rr * 2.1, self.lit(c, N, V(0.05, 0.05, 0.06)), ang=0.0, stretch=1.0)
                    cv.dab(pc[0] - rr * 0.25, pc[1] - rr * 0.3, rr * 0.9, self.lit(c, N, V(0.45, 0.45, 0.5), gloss=0.8), ang=0.3, stretch=1.3)
                    continue
                tone = 0.86 - 0.52 * smooth(0.05, 1.0, (u0 + u1) / 2) ** 1.25      # white at one end, grey at the other
                g, lift = 0.012, 0.0085
                c = top((u0 + u1) / 2, (v0 + v1) / 2, lift)
                # the cap's front wall, in its own shadow, then its top
                fa, fb = P(top(u0 + g, v1 - 0.01, lift * 0.35)), P(top(u1 - g, v1 - 0.01, lift * 0.35))
                wall_c = self.lit(c, kb.R[:, 2], V(tone, tone, tone * 1.02) * 0.62, samples=3)
                cv.line(fa, fb, max(2.0, self.px(c, 0.0065)), wall_c, dry=0.1, rag=1.0, soft=0.2, taper=(0.02, 0.02), jitter=0.03)
                ta, tb = P(top(u0 + g, (v0 + v1) / 2 - 0.012, lift)), P(top(u1 - g, (v0 + v1) / 2 - 0.012, lift))
                top_c = self.lit(c, N, V(tone, tone, tone * 1.02), samples=4, gloss=0.25)
                cv.line(ta, tb, max(2.4, self.px(c, 0.0135)), top_c, dry=0.12, rag=1.2, soft=0.22, taper=(0.02, 0.02), jitter=0.045)

    # ------------------------------------------------------------------ notebook
    def notebook(self, fine=False):
        cv, S, bk, P, r = self.cv, self.S, self.book, self.P, self.r
        N = bk.R[:, 1]
        paper = V(0.86, 0.83, 0.72)
        if not fine:
            self.box(bk, {"+y": paper, "+z": paper * 0.8, "-x": V(0.10, 0.12, 0.28), "+x": paper * 0.8, "-z": paper * 0.8,
                          "-y": None}, w=11, l=54, dry=0.25, dirs={"+y": bk.R[:, 2]})
            return
        top = lambda u, v: bk.at(u * 2 - 1, 1.05, v * 2 - 1)                                # noqa: E731
        ink = V(0.10, 0.12, 0.30)
        for j in range(13):                                             # what i expect, written before i run it
            v = 0.09 + j * 0.066
            u = 0.10
            for k in range(int(r.integers(2, 5))):
                u1 = min(0.92, u + r.uniform(0.08, 0.26))
                if j in (4, 9):
                    break
                c = top((u + u1) / 2, v)
                cv.line(P(top(u, v)), P(top(u1, v)), 2.0 * S, self.lit(c, N, ink, samples=2), alpha=0.8, dry=0.45,
                        bow=r.normal(0, 0.03), scumble=0.12)
                u = u1 + 0.04
                if u > 0.86:
                    break
        c = top(0.60, 0.33)                                             # one number, boxed
        col = self.lit(c, N, V(0.62, 0.12, 0.08), samples=2)
        bx = [top(0.52, 0.275), top(0.90, 0.275), top(0.90, 0.385), top(0.52, 0.385)]
        for i in range(4):
            cv.line(P(bx[i]), P(bx[(i + 1) % 4]), 2.0 * S, col, alpha=0.85, dry=0.4, bow=r.normal(0, 0.02))
        # the pen, across the page
        a3, b3 = bk.at(-0.55, 1.6, 0.55), bk.at(0.75, 1.6, -0.15)
        self.tube([a3, b3], 0.0045, self.lit((a3 + b3) / 2, N, V(0.06, 0.10, 0.34)), self.lit((a3 + b3) / 2, N, V(0.55, 0.62, 0.9), gloss=0.6))
        tip = P(b3)
        cv.dab(tip[0], tip[1], 4 * S, self.lit(b3, N, V(0.7, 0.7, 0.72), gloss=0.5), ang=None)

    # ------------------------------------------------------------- raspberry pi
    def raspberry(self, fine=False):
        cv, S, pi, P, r = self.cv, self.S, self.pi, self.P, self.r
        N = pi.R[:, 1]
        top = lambda u, v, lift=0.0: pi.at(u * 2 - 1, 1 + lift / pi.h[1], v * 2 - 1)        # noqa: E731
        if not fine:
            self.box(pi, V(0.07, 0.36, 0.19), w=6, l=30, dry=0.2, gloss=0.3)
            return
        silver, black = V(0.70, 0.70, 0.72), V(0.04, 0.04, 0.05)
        parts = [  # centre u, v on the board; size in metres x, y, z; colour
            (0.86, 0.19, (0.021, 0.0135, 0.016), silver), (0.87, 0.52, (0.0175, 0.016, 0.0135), silver),
            (0.87, 0.82, (0.0175, 0.016, 0.0135), silver), (0.40, 0.52, (0.017, 0.003, 0.017), V(0.55, 0.56, 0.58)),
            (0.36, 0.085, (0.051, 0.0085, 0.005), black), (0.13, 0.90, (0.009, 0.0032, 0.0075), silver),
            (0.60, 0.80, (0.012, 0.002, 0.012), black),
        ]
        yaw = math.atan2(-pi.R[2, 0], pi.R[0, 0])
        for u, v, sz, col in parts:
            c = top(u, v, sz[1] / 2 + 0.0005)
            self.box(Box(c, sz, yaw=yaw), col, w=3.2, l=13, dry=0.15, samples=3, gloss=0.4, coljit=0.03)
        for i in range(12):                                             # the pins
            c = top(0.13 + i * 0.042, 0.085, 0.011)
            p = P(c)
            cv.dab(p[0], p[1], 2.4 * S, self.lit(c, N, V(0.85, 0.66, 0.25), gloss=0.6, samples=2), ang=1.57, stretch=1.2)
        for u, v, col in [(0.06, 0.60, hexc("ff3b2f")), (0.06, 0.70, hexc("5dff8a"))]:   # power, activity
            p = P(top(u, v, 0.002))
            if self.night:
                cv.dab(p[0], p[1], 14 * S, col, ang=0, stretch=1.0, alpha=0.20, glaze=True, soft=0.9)
            cv.dab(p[0], p[1], 3.6 * S, col * (1.0 if self.night else 0.8) + 0.12, ang=0, stretch=1.0, dry=0.0)
        # its power lead, off toward the wall
        a = top(0.13, 1.0, 0.002)
        pts = [a, a + V(-0.02, -0.012, 0.035), a + V(-0.09, -0.016, 0.02), a + V(-0.17, -0.016, -0.06), a + V(-0.21, -0.016, -0.19)]
        self.tube(pts, 0.0028, self.lit(pts[2], V(0, 1, 0), V(0.85, 0.85, 0.85)), None)

    # ------------------------------------------------------------------ the plant
    def plant(self, fine=False):
        """something growing in an old tin, under the window."""
        cv, S, P, r, tin = self.cv, self.S, self.P, self.r, self.tin
        if not fine:
            up = V(0, 1, 0)
            self.box(tin, V(0.62, 0.60, 0.56), w=7, l=40, dry=0.2, gloss=0.25, dirs={"+z": up, "-x": up, "+x": up})
            return
        for name, q, n in tin.visible(self.cam):                       # what is left of the label
            if name in ("+z", "+x", "-x"):
                band = [q[0] + (q[3] - q[0]) * 0.22, q[1] + (q[2] - q[1]) * 0.22, q[1] + (q[2] - q[1]) * 0.70, q[0] + (q[3] - q[0]) * 0.70]
                self.plane_fill(band, n, V(0.80, 0.56, 0.10), tin.R[:, 0] if name == "+z" else tin.R[:, 2], 6, 26, dry=0.45, samples=3)
        top = tin.at(0, 1, 0)
        self.plane_fill(tin.face("+y")[0], tin.R[:, 1], V(0.10, 0.07, 0.05), tin.R[:, 0], 5, 20, dry=0.2)
        leaves = [(-0.085, 0.20, 0.02), (-0.03, 0.27, -0.01), (0.03, 0.30, 0.02), (0.085, 0.22, 0.03), (0.12, 0.13, 0.05),
                  (-0.12, 0.11, 0.04), (0.0, 0.19, 0.06), (0.055, 0.15, 0.07), (-0.05, 0.14, 0.07)]
        for dx, dy, dz in leaves:
            tip = top + V(dx, dy, dz)
            mid = top + V(dx * 0.35, dy * 0.62, dz * 0.5)
            green = V(0.10, 0.36, 0.14) * r.uniform(0.8, 1.25)
            col = self.lit(mid, unit(V(0.2, 0.5, 0.8)), green, samples=3)
            a, m, b = P(top), P(mid), P(tip)
            w = self.px(mid, 0.026)
            cv.stroke(bezier(a, m, b, 8), w, col, dry=0.3, jitter=0.07, taper=(0.5, 0.55), rag=w * 0.2)
            cv.stroke(bezier(a, m, b, 8), max(1.4, w * 0.12), self.lit(mid, unit(BULB - mid), green * 2.0, samples=1),
                      dry=0.3, alpha=0.7, rag=2)

    # ------------------------------------------------------------ the year planner
    def planner(self, fine=False):
        """a year planner pinned to the wall: 365 boxes, one crossed off for every day in
        the log. it reads data.js, so the picture is only right on the day it was painted."""
        cv, S, P, r = self.cv, self.S, self.P, self.r
        x0, x1, y0, y1 = 0.47, 0.93, 0.915, 1.215
        Nz = V(0, 0, 1)
        g = lambda u, v: V(x0 + (x1 - x0) * u, y1 - (y1 - y0) * v, 0.004)                   # noqa: E731
        if not fine:
            self.plane_fill([g(0, 0), g(1, 0), g(1, 1), g(0, 1)], Nz, V(0.90, 0.88, 0.80), V(1, 0, 0), 15, 80, dry=0.2,
                            coljit=0.025)
            self.plane_fill([g(0, 0), g(1, 0), g(1, 0.13), g(0, 0.13)], Nz, V(0.10, 0.20, 0.42), V(1, 0, 0), 9, 70, dry=0.2)
            return
        cols, rows = 31, 12
        done, rest = logged_days()
        n = 0
        for j in range(rows):
            for i in range(cols):
                if n >= 365:
                    break
                n += 1
                u, v = 0.045 + i * 0.0297, 0.20 + j * 0.064
                c = g(u + 0.011, v + 0.022)
                if n in done or n in rest:
                    col = self.lit(c, Nz, V(0.70, 0.10, 0.06) if n in done else V(0.35, 0.40, 0.55), samples=2)
                    a, b = P(g(u, v + 0.042)), P(g(u + 0.022, v + 0.004))
                    cv.line(a, b, 2.6 * S, col, dry=0.2, rag=1.0, bow=r.normal(0, 0.05))
                    if n in done:
                        a, b = P(g(u, v + 0.004)), P(g(u + 0.022, v + 0.042))
                        cv.line(a, b, 2.4 * S, col, dry=0.3, rag=1.0, bow=r.normal(0, 0.05))
                else:
                    p = P(c)
                    cv.dab(p[0], p[1], 2.3 * S, self.lit(c, Nz, V(0.55, 0.56, 0.58), samples=1), ang=0, stretch=1.0, alpha=0.7)
        for u in (0.06, 0.94):                                          # masking tape, top corners
            c = g(u, 0.0)
            p = P(c)
            cv.dab(p[0], p[1], 15 * S, self.lit(c, Nz, V(0.86, 0.80, 0.56), samples=2), ang=0.5 if u < 0.5 else -0.5, stretch=1.9, alpha=0.9)
        for k in range(5):                                              # the heading, lettered in white
            a, b = P(g(0.06 + k * 0.10, 0.065)), P(g(0.06 + k * 0.10 + 0.07, 0.065))
            cv.line(a, b, 3.4 * S, self.lit(g(0.3, 0.06), Nz, V(0.95, 0.95, 0.92), samples=1), dry=0.25)

    # ---------------------------------------------- the meter, the socket, trunking
    def meter_wall(self, fine=False):
        cv, S, m, P = self.cv, self.S, self.meter, self.P
        white = V(0.86, 0.86, 0.82)
        Nz = V(0, 0, 1)
        if not fine:
            # pvc trunking along the wall with a drop to the socket
            mx = self.meter.c[0]
            for a, b, vert in [((mx - 0.10, 1.262), (1.7, 1.284), False), ((mx - 0.011, 1.14), (mx + 0.011, 1.262), True)]:
                q = [V(a[0], b[1], 0.012), V(b[0], b[1], 0.012), V(b[0], a[1], 0.012), V(a[0], a[1], 0.012)]
                self.plane_fill(q, Nz, white, V(0, 1, 0) if vert else V(1, 0, 0), 8, 60, dry=0.3, coljit=0.03)
            plate = [V(mx - 0.055, 1.145, 0.006), V(mx + 0.055, 1.145, 0.006), V(mx + 0.055, 1.005, 0.006), V(mx - 0.055, 1.005, 0.006)]
            self.plane_fill(plate, Nz, white * 0.96, V(1, 0, 0), 8, 30, dry=0.2)
            self.box(m, white, w=7, l=30, dry=0.2, coljit=0.025)
            self.box(self.brick, V(0.05, 0.05, 0.06), w=7, l=30, dry=0.2, gloss=0.05)
            return
        # under the trunking, its own thin shadow
        a, b = P(V(self.meter.c[0] - 0.10, 1.258, 0.001)), P(V(1.7, 1.258, 0.001))
        cv.line(a, b, 2.4 * S, self.sc.tone(V(0.03, 0.04, 0.07)), alpha=0.6, dry=0.4)
        g = lambda u, v: m.at(u * 2 - 1, 1 - v * 2, 1.03)                                  # noqa: E731
        lcd = [g(0.14, 0.13), g(0.86, 0.13), g(0.86, 0.46), g(0.14, 0.46)]
        glow = hexc("b9e6c0") if self.night else hexc("9fb7a2")
        cv.fill([P(p) for p in lcd], glow, 0.0, 5 * S, 22 * S, density=1.4, dry=0.1, coljit=0.02)
        if self.night:
            c = P(g(0.5, 0.3))
            cv.dab(c[0], c[1], 60 * S, glow, ang=0, stretch=1.3, alpha=0.10, glaze=True, soft=0.95)
        seg7(cv, [P(g(0.20, 0.19)), P(g(0.36, 0.19)), P(g(0.36, 0.41)), P(g(0.20, 0.41))], "3", hexc("12241a"), 2.3 * S)
        seg7(cv, [P(g(0.40, 0.19)), P(g(0.56, 0.19)), P(g(0.56, 0.41)), P(g(0.40, 0.41))], "8", hexc("12241a"), 2.3 * S)
        d = P(g(0.60, 0.41))
        cv.dab(d[0], d[1], 2.6 * S, hexc("12241a"), ang=0, stretch=1.0)
        seg7(cv, [P(g(0.64, 0.19)), P(g(0.80, 0.19)), P(g(0.80, 0.41)), P(g(0.64, 0.41))], "4", hexc("12241a"), 2.3 * S)
        for u in (0.26, 0.5, 0.74):                                     # three buttons under the glass
            c = g(u, 0.62)
            p = P(c)
            cv.dab(p[0], p[1], 6.5 * S, self.lit(c, Nz, V(0.30, 0.42, 0.62), samples=2), ang=0, stretch=1.25)
        # the lead: meter -> brick -> laptop
        b0 = m.at(0, -1, 0.3)
        k0 = self.brick.at(1, 0.2, 0)
        lead = self.lit(V(0.38, DESK, 0.12), V(0, 1, 0), V(0.04, 0.04, 0.05))
        self.tube([b0, b0 + V(0.01, -0.14, 0.03), V(b0[0] + 0.05, DESK + 0.006, 0.07), V(b0[0] + 0.10, DESK + 0.004, 0.13), k0], 0.0032, lead)
        k1 = self.brick.at(-1, 0.2, 0)
        jack = self.lap.at(1, 0.2, -0.55)
        self.tube([k1, k1 + V(-0.05, -0.008, 0.05), jack + V(0.06, 0.0, 0.03), jack], 0.0024, lead)
        hi = P(self.brick.at(0, 1.05, 0))
        cv.dab(hi[0], hi[1], 4 * S, hexc("7dff9a") if self.night else hexc("7fbf8a"), ang=0, stretch=1.0)

    # ------------------------------------------------------------- the phone rig
    def rig(self, fine=False):
        cv, S, P = self.cv, self.S, self.P
        black = V(0.045, 0.045, 0.055)
        if not fine:
            self.box(self.rigbase, black, w=9, l=40, dry=0.2, gloss=0.06)
            self.box(self.stem, black * 1.2, w=7, l=40, dry=0.2, gloss=0.05, dirs={"+z": V(0, 1, 0), "-x": V(0, 1, 0), "+x": V(0, 1, 0)})
            return
        mid = self.neck_pts[6]
        dark = self.lit(mid, unit(V(0, 0.3, 1)), black, samples=3)
        hi = self.lit(mid, unit(BULB - mid), V(0.40, 0.40, 0.44), samples=1, gloss=0.5)
        self.tube(self.neck_pts, 0.0072, dark, hi, n=7)
        # the cradle and the phone, looking down at the hands
        ph = self.phone
        back, rim = V(0.66, 0.64, 0.80), V(0.5, 0.5, 0.55)                # lilac glass, steel rim
        self.box(ph, {"-z": back, "+z": V(0.02, 0.02, 0.03), "+x": rim, "-x": rim, "+y": rim, "-y": rim},
                 w=6, l=34, dry=0.18, gloss=0.5, dirs={"+z": ph.R[:, 1], "-z": ph.R[:, 1]})
        for name, q, n in ph.visible(self.cam):
            if name == "-z":
                for lx, ly in [(0.52, 0.74), (0.52, 0.50), (0.52, 0.26)]:
                    c = ph.at(lx, ly, -1.3)
                    p = P(c)
                    rr = self.px(c, 0.011)
                    cv.dab(p[0], p[1], rr, V(0.03, 0.03, 0.05), ang=0, stretch=1.0)
            if name == "+z":                # its screen: the bench again, small, as the camera sees it
                g = lambda u, v: ph.at(u * 2 - 1, 1 - v * 2, 1.3)        # noqa: E731
                k = 1.0 if self.night else 0.6
                cv.fill([P(g(0.07, 0.05)), P(g(0.93, 0.05)), P(g(0.93, 0.95)), P(g(0.07, 0.95))], hexc("a8652f") * k, 0.3,
                        5 * S, 20 * S, dry=0.1, density=1.3)
                cv.fill([P(g(0.07, 0.05)), P(g(0.93, 0.05)), P(g(0.93, 0.30)), P(g(0.07, 0.30))], hexc("1b2a4d") * k, 0.3,
                        5 * S, 20 * S, dry=0.1, density=1.3)
                cv.fill([P(g(0.20, 0.36)), P(g(0.80, 0.36)), P(g(0.80, 0.50)), P(g(0.20, 0.50))], hexc("2a2f3a") * k, 0.3,
                        4 * S, 16 * S, dry=0.1)
                cv.fill([P(g(0.16, 0.60)), P(g(0.84, 0.60)), P(g(0.84, 0.78)), P(g(0.16, 0.78))], hexc("f1e3c2") * k, 0.3,
                        4 * S, 16 * S, dry=0.1)
                d = P(g(0.86, 0.10))
                cv.dab(d[0], d[1], 3.2 * S, hexc("ff3b2f"), ang=0, stretch=1.0)   # it is recording
        # the clamp's two jaws
        for ly in (-1.0, 1.0):
            a, b = ph.at(-1.1, ly, 0.0), ph.at(1.1, ly, 0.0)
            self.tube([a, b], 0.006, self.lit(a, unit(V(0, 0.4, 1)), black, samples=2))
        a = self.neck_pts[-1]
        self.tube([a, ph.at(0, 0, -1.6)], 0.008, dark)

    # ------------------------------------------------------- the bulb, the moths
    def bulb(self, fine=False):
        cv, S, r, P = self.cv, self.S, self.r, self.P
        bp = np.array(P(BULB))
        rr = self.px(BULB, 0.030)
        cord = hexc("05060d") if self.night else hexc("2a2a30")
        if not fine:
            cv.stroke(bezier((bp[0] + 5 * S, -30), (bp[0] - 4 * S, bp[1] * 0.5), (bp[0], bp[1] - rr * 2.6), 8), 4.2 * S, cord, dry=0.1, jitter=0.02)
            return
        if self.night:
            # the air round the lamp: thin warm glazes, ring on ring
            for k, (mul, al) in enumerate([(7.0, 0.05), (5.2, 0.07), (3.8, 0.10), (2.7, 0.15), (1.9, 0.24)]):
                n = int(9 + mul * 2)
                for i in range(n):
                    a0 = r.uniform(0, 6.283)
                    arc = circle(bp, rr * mul * r.uniform(0.82, 1.0), a0, a0 + r.uniform(0.7, 1.3), 7)
                    cv.stroke(arc, rr * mul * 0.55, hexc("ffb347") if k < 3 else hexc("ffd58a"), alpha=al, glaze=True,
                              soft=0.9, dry=0.2, jitter=0.02, rag=rr)
        # holder
        hc = P(BULB + V(0, 0.062, 0))
        hw = self.px(BULB, 0.034)
        cv.line((hc[0], hc[1] - hw * 0.8), (hc[0], hc[1] + hw * 0.75), hw, cord * 1.0 + (0.02 if self.night else 0.0), dry=0.05, rag=1, taper=(0.02, 0.02))
        if self.night:
            cv.line((hc[0] - hw * 0.33, hc[1] + hw * 0.1), (hc[0] - hw * 0.33, hc[1] + hw * 0.7), hw * 0.18, hexc("c9712f"), alpha=0.8, dry=0.3)
            # the glass: thick paint, hottest at the heart
            for mul, c, n in [(1.12, "ff9d2e", 9), (0.96, "ffc45a", 8), (0.80, "ffe7ae", 7), (0.60, "fff6dc", 5), (0.36, "ffffff", 3)]:
                for i in range(n):
                    a0 = 6.283 * i / n + r.uniform(-0.3, 0.3)
                    d = rr * mul * 0.42
                    cv.dab(bp[0] + math.cos(a0) * d, bp[1] + rr * 0.08 + math.sin(a0) * d, rr * mul * 0.95, hexc(c),
                           ang=a0 + 1.57, stretch=1.25, dry=0.08, jitter=0.03, thick=1.7, soft=0.3)
        else:
            for mul, c in [(1.0, "c9d2d6"), (0.75, "e6ecee"), (0.4, "f7fafb")]:
                for i in range(6):
                    a0 = r.uniform(0, 6.283)
                    cv.stroke(circle(bp + [0, rr * 0.08], rr * mul * 0.55, a0, a0 + 2.6, 7), rr * mul * 0.9, hexc(c), dry=0.12, jitter=0.03)
            cv.dab(bp[0] - rr * 0.35, bp[1] - rr * 0.1, rr * 0.4, hexc("ffffff"), ang=1.2, stretch=1.8)
            cv.line((bp[0] - 2 * S, bp[1] - rr * 0.5), (bp[0] + 2 * S, bp[1] + rr * 0.3), 1.6 * S, hexc("7a7f86"), alpha=0.8)

    def moths(self):
        """the cast from the old hero: elephant hawk-moth, rosy maple, luna, garden tiger."""
        if not self.night:
            return
        cv, S, r, P = self.cv, self.S, self.r, self.P
        cast = [  # where, wing colour, body colour, wingspan m, heading, on the wall?
            (BULB + V(0.115, 0.045, 0.02), hexc("d9799c"), hexc("8a8a3a"), 0.040, 0.6, False),
            (BULB + V(-0.135, -0.055, 0.03), hexc("f3d3da"), hexc("f1d873"), 0.028, 2.5, False),
            (BULB + V(0.055, -0.150, 0.05), hexc("bfe3c0"), hexc("f4f4e0"), 0.046, -1.2, False),
            (V(BULB[0] + 0.335, BULB[1] - 0.115, 0.004), hexc("efe6d4"), hexc("c2551f"), 0.036, 1.9, True),
        ]
        self.moth_spots = []
        for pos, wing, body, span, head, resting in cast:
            p = np.array(P(pos))
            w = self.px(pos, span)
            lt = self.sc.light(pos, unit(BULB - pos), samples=1)[0]
            k = float(np.clip(1 - math.exp(-1.6 * lt.mean()), 0.35, 1.0))
            if resting:                                                  # its shadow on the plaster
                away = unit(V(pos[0] - BULB[0], pos[1] - BULB[1], 0))
                sp = np.array(P(pos + away * 0.012))
                for sgn in (-1, 1):
                    cv.dab(sp[0] + math.cos(head + sgn * 1.2) * w * 0.3, sp[1] + math.sin(head + sgn * 1.2) * w * 0.3,
                           w * 0.42, self.sc.tone(V(0.03, 0.04, 0.08)), ang=head + sgn * 0.55, stretch=1.7, alpha=0.7, dry=0.3)
            hx, hy = math.cos(head), math.sin(head)
            for sgn in (-1, 1):
                nx, ny = -hy * sgn, hx * sgn
                c = p + np.array([nx, ny]) * w * 0.30 + np.array([hx, hy]) * w * 0.05
                cv.dab(c[0], c[1], w * 0.40, wing * k, ang=head + sgn * (0.5 if resting else 1.0), stretch=1.75, dry=0.3,
                       jitter=0.08, thick=1.3)
                c2 = p + np.array([nx, ny]) * w * 0.20 - np.array([hx, hy]) * w * 0.20
                cv.dab(c2[0], c2[1], w * 0.25, wing * k * 0.82, ang=head - sgn * 0.4, stretch=1.5, dry=0.3, jitter=0.08)
            cv.line(p - np.array([hx, hy]) * w * 0.22, p + np.array([hx, hy]) * w * 0.20, max(2.0, w * 0.13), body * k, dry=0.1)
            self.moth_spots.append((float(p[0] / self.W), float(p[1] / self.H)))

    def spots(self):
        """where things are on the canvas, 0..1, so the page can make them doors."""
        def around(pts, pad=0.012):
            q = np.array([self.P(p) for p in pts])
            x0, y0 = q[:, 0].min() / self.W - pad, q[:, 1].min() / self.H - pad * 2
            x1, y1 = q[:, 0].max() / self.W + pad, q[:, 1].max() / self.H + pad * 2
            x0, y0, x1, y1 = max(0.02, x0), max(0.03, y0), min(0.98, x1), min(0.97, y1)
            return [round(float(v), 4) for v in (x0, y0, x1 - x0, y1 - y0)]

        def corners(*boxes):
            return [b.at(i, j, k) for b in boxes for i in (-1, 1) for j in (-1, 1) for k in (-1, 1)]
        t = self.tin.at(0, 1, 0)
        return {
            "planner": around([V(0.47, 0.915, 0), V(0.93, 1.215, 0)]),
            "notebook": around(corners(self.book)),
            "plant": around(corners(self.tin) + [t + V(-0.12, 0.30, 0), t + V(0.12, 0.30, 0)]),
            "laptop": around(corners(self.lap, self.scr)),
            "keys": around(corners(self.kbd)),
            "meter": around(corners(self.meter), 0.02),
            "rig": around(corners(self.phone), 0.016),
            "pi": around(corners(self.pi), 0.02),
            "bulb": around([BULB + V(-0.05, -0.05, 0), BULB + V(0.05, 0.09, 0)], 0.01),
        }

    # ---------------------------------------------------------------- the picture
    def paint(self, log=print):
        cv = self.cv
        t = time.time()
        self.underdrawing()
        self.under = cv.render(relief=0)
        self.n_under = cv.n
        cv.paint_frame(int((46 if self.view in ("wide", "tall") else 30) * self.S))
        first = [self.wall, self.window, self.desk]           # the room itself, taken to a finish
        things = [self.planner, self.meter_wall, self.plant, self.raspberry, self.laptop, self.notebook, self.keyboard, self.rig, self.bulb]
        for f in first:
            f(False)
            f(True)
            log(f"  {f.__name__:11s} laid in      {cv.n:6d} strokes  {time.time() - t:5.1f}s")
        for f in things:                                # block in: every object, one decision a face
            f(False)
        log(f"  objects     blocked in   {cv.n:6d} strokes  {time.time() - t:5.1f}s")
        self.block = cv.render()
        self.n_block = cv.n
        self.order_block = cv.order.copy()
        for f in things:                                # then the small things
            f(True)
            log(f"  {f.__name__:11s} finished     {cv.n:6d} strokes  {time.time() - t:5.1f}s")
        self.moths()
        self.final = cv.render()
        log(f"  done: {cv.n} strokes, {time.time() - t:.1f}s")
        return self.final


# ------------------------------------------------------------------- small tools
def spline3(pts, n=6):
    p = np.asarray(pts, np.float64)
    p = np.vstack([2 * p[0] - p[1], p, 2 * p[-1] - p[-2]])
    out = []
    for i in range(1, len(p) - 2):
        for k in range(n):
            t = k / n
            a, b, c, d = p[i - 1], p[i], p[i + 1], p[i + 2]
            out.append(0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t * t + (-a + 3 * b - 3 * c + d) * t ** 3))
    out.append(p[-2])
    return out


def circle(c, rad, a0=0.0, a1=6.283, n=24):
    a = np.linspace(a0, a1, n, dtype=F)
    return np.stack([c[0] + np.cos(a) * rad, c[1] + np.sin(a) * rad], axis=1)


def clip_poly(poly, x0, y0, x1, y1):
    """sutherland-hodgman: a polygon cut to a rectangle."""
    def cut(pts, inside, cross):
        out = []
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            ia, ib = inside(a), inside(b)
            if ia:
                out.append(a)
            if ia != ib:
                out.append(cross(a, b))
        return out
    def xi(a, b, x): t = (x - a[0]) / (b[0] - a[0]); return (x, a[1] + t * (b[1] - a[1]))    # noqa: E704
    def yi(a, b, y): t = (y - a[1]) / (b[1] - a[1]); return (a[0] + t * (b[0] - a[0]), y)    # noqa: E704
    p = [tuple(q) for q in poly]
    p = cut(p, lambda q: q[0] >= x0, lambda a, b: xi(a, b, x0))
    p = cut(p, lambda q: q[0] <= x1, lambda a, b: xi(a, b, x1))
    p = cut(p, lambda q: q[1] >= y0, lambda a, b: yi(a, b, y0))
    p = cut(p, lambda q: q[1] <= y1, lambda a, b: yi(a, b, y1))
    return p


def logged_days():
    """working days in the log, split into days worked and days rested."""
    try:
        import json
        src = open(os.path.join(ROOT, "data.js"), encoding="utf-8").read()
        days = json.loads(src[src.index("window.DS=") + 10:].rstrip().rstrip(";"))["days"]
        rest = {d["d"] for d in days if d["msg"].strip().lower() in ("rest", "rest day")}
        return {d["d"] for d in days} - rest, rest
    except Exception:
        return set(), set()


SEG = {"0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc", "5": "afgcd", "6": "afgedc", "7": "abc",
       "8": "abcdefg", "9": "abfgcd"}


def seg7(cv, quad, ch, color, w):
    tl, tr, br, bl = [np.asarray(q, F) for q in quad]
    ml, mr = (tl + bl) / 2, (tr + br) / 2
    segs = {"a": (tl, tr), "b": (tr, mr), "c": (mr, br), "d": (bl, br), "e": (ml, bl), "f": (tl, ml), "g": (ml, mr)}
    for s in SEG[ch]:
        a, b = segs[s]
        cv.line(a + (b - a) * 0.12, b - (b - a) * 0.12, w, color, dry=0.05, rag=0.4, taper=(0.02, 0.02), soft=0.3, jitter=0)


def save(img, path, q=None):
    bgr = cv2.cvtColor((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8), cv2.COLOR_RGB2BGR)
    cv2.imwrite(path, bgr, [cv2.IMWRITE_WEBP_QUALITY, q] if q else [])


def write_assets(p, base, out, replay=True, q=82):
    """save a finished painter's picture, and (for the ones the site replays) what the
    page needs to replay it: the block-in, the pencil, and when each pixel was painted."""
    cv = p.cv
    rs = lambda img, size: cv2.resize(img, size, interpolation=cv2.INTER_AREA)     # noqa: E731
    meta = {"w": out[0], "h": out[1], "strokes": int(cv.n)}
    if not replay:
        save(rs(p.final, out), base + ".webp", 80)
        return meta
    small = (out[0] // 2, out[1] // 2)
    save(rs(p.final, out), base + ".webp", q)
    save(rs(p.block, small), base + "-block.webp", 62)
    save(rs(p.under, small), base + "-under.webp", 70)
    # when each pixel was painted: red for the block-in, green for the finish
    o1 = np.clip((p.order_block - p.n_under) / max(1, p.n_block - p.n_under), 0, 1)
    o2 = np.where(cv.order > p.n_block, (cv.order - p.n_block) / max(1, cv.n - p.n_block), 0)
    o2 = np.where(cv.order > p.n_block, np.maximum(o2, 1 / 255), 0)
    om = np.stack([o1, o2, np.zeros_like(o1)], axis=2).astype(F)
    om = cv2.resize(om, small, interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(base + "-order.png", cv2.cvtColor((om * 255 + 0.5).astype(np.uint8), cv2.COLOR_RGB2BGR),
                [cv2.IMWRITE_PNG_COMPRESSION, 9])
    return meta


def export(job):
    """paint one picture of the bench and write what the site needs to show it."""
    mode, view = job
    p = Painter(mode, view)
    p.paint(log=lambda *_: None)
    base = os.path.join(ROOT, "art", f"bench-{mode}-{view}")
    replay = view in ("wide", "tall")
    meta = write_assets(p, base, VIEWS[view][6], replay)
    if replay:
        bp = p.P(BULB)
        meta.update({"bulb": [round(bp[0] / p.W, 4), round(bp[1] / p.H, 4)], "bulb_r": round(p.px(BULB, 0.03) / p.W, 4),
                     "spots": p.spots()})
    return f"{mode}-{view}", meta


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opt = {sys.argv[i]: sys.argv[i + 1] for i in range(1, len(sys.argv) - 1) if sys.argv[i].startswith("--")}
    if not args:
        import json
        from multiprocessing import Pool
        os.makedirs(os.path.join(ROOT, "art"), exist_ok=True)
        jobs = [(m, v) for m in ("night", "day") for v in VIEWS]
        t = time.time()
        with Pool(min(6, os.cpu_count() or 1)) as pool:
            meta = dict(pool.map(export, jobs))
        done, rest = logged_days()
        meta["days"] = len(done) + len(rest)
        meta["ground"] = GROUND
        with open(os.path.join(ROOT, "art", "bench.js"), "w") as f:
            f.write("/* written by _tools/paint/bench.py. the pictures, and what the page needs to replay them */\n")
            f.write("window.DSART=" + json.dumps(meta, separators=(",", ":")) + ";\n")
        for k, v in meta.items():
            if isinstance(v, dict) and "strokes" in v:
                print(f"  {k:11s} {v['strokes']} strokes")
        print(f"  painted in {time.time() - t:.0f}s")
        sys.exit(0)
    mode = args[0]
    view = args[1] if len(args) > 1 else "wide"
    p = Painter(mode, view, float(opt.get("--scale", 1.0)))
    p.paint()
    if "--preview" in opt:
        save(p.final, opt["--preview"])
        if "--under" in opt:
            save(p.under, opt["--under"])
