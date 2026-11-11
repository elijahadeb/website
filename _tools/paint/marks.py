#!/usr/bin/env python3
"""marks.py — the small painted marks the pages use: a long dry rule, a swash to sit
behind a word, and a strip of single dabs (one per day of the year on the home page).

each is one white stroke saved as a transparency mask, so css can tint it to
whatever the page's ink is. run it again and the marks come out the same."""
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Canvas, spline                                            # noqa: E402

ART = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "art")


def mask(cv, path):
    a = (np.clip(cv.rgb[..., 0], 0, 1) * 255 + 0.5).astype(np.uint8)
    rgba = np.dstack([np.full_like(a, 255)] * 3 + [a])
    cv2.imwrite(path, rgba, [cv2.IMWRITE_PNG_COMPRESSION, 9])


def rule():
    cv = Canvas(1600, 24, (0, 0, 0), seed=21)
    cv.stroke(spline([(14, 12), (400, 10.5), (800, 13), (1200, 11), (1580, 12.5)], 6), 9, (1, 1, 1), dry=0.62,
              jitter=0, rag=22, taper=(0.02, 0.3), soft=0.2)
    mask(cv, os.path.join(ART, "rule.png"))


def swash():
    cv = Canvas(480, 72, (0, 0, 0), seed=22)
    cv.stroke(spline([(12, 40), (150, 33), (320, 38), (468, 34)], 6), 52, (1, 1, 1), dry=0.42, jitter=0, rag=16,
              taper=(0.05, 0.2), soft=0.12)
    mask(cv, os.path.join(ART, "swash.png"))


def dabs(n=12, w=24, h=40):
    cv = Canvas(n * w, h, (0, 0, 0), seed=23)
    r = cv.rng
    for i in range(n):
        x = i * w + w / 2
        cv.stroke([(x + r.normal(0, 1.0), 5 + r.uniform(0, 3)), (x + r.normal(0, 1.2), h - 5 - r.uniform(0, 3))],
                  w * 0.66, (1, 1, 1), dry=r.uniform(0.25, 0.6), jitter=0, rag=3.5, taper=(0.12, 0.3), soft=0.16, nb=7)
    mask(cv, os.path.join(ART, "dabs.png"))


if __name__ == "__main__":
    os.makedirs(ART, exist_ok=True)
    rule(), swash(), dabs()
    print("  rule.png, swash.png, dabs.png")
