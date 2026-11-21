#!/usr/bin/env python3
"""One image that sums up the world news of Saturday 21 November 2026.

The poster is a broadsheet front page rendered entirely by this program:
a small RGB canvas, a hand-drawn 6x8 bitmap typeface and a from-scratch
PNG writer.  Pure Python standard library, no network, no clock, no
randomness -- every run produces exactly the same bytes.

Layout is data-driven: the page is a list of section dictionaries and a
single walker paints them top to bottom, asking each section how tall it
is and then handing it a strip of the page to fill.
"""

import binascii
import os
import struct
import zlib

PAGE_W = 1024
PAGE_H = 1024
MARGIN = 36
COL_W = PAGE_W - 2 * MARGIN

PAPER = (247, 243, 232)
INK = (27, 25, 23)
FAINT = (108, 100, 90)
RED = (172, 30, 38)
NAVY = (29, 52, 99)
GOLD = (188, 138, 38)
GREEN = (33, 104, 62)
ORANGE = (219, 106, 26)
SMOKE = (140, 134, 126)
WHITE = (252, 250, 244)

# ---------------------------------------------------------------------------
# 6x8 bitmap typeface.  Each glyph is eight strings of six cells; '#' is ink.
# ---------------------------------------------------------------------------

GLYPHS = {
    "A": (".####.", "#....#", "#....#", "######", "#....#", "#....#", "#....#", "#....#"),
    "B": ("#####.", "#....#", "#....#", "#####.", "#....#", "#....#", "#....#", "#####."),
    "C": (".####.", "#....#", "#.....", "#.....", "#.....", "#.....", "#....#", ".####."),
    "D": ("#####.", "#....#", "#....#", "#....#", "#....#", "#....#", "#....#", "#####."),
    "E": ("######", "#.....", "#.....", "#####.", "#.....", "#.....", "#.....", "######"),
    "F": ("######", "#.....", "#.....", "#####.", "#.....", "#.....", "#.....", "#....."),
    "G": (".####.", "#....#", "#.....", "#.####", "#....#", "#....#", "#....#", ".####."),
    "H": ("#....#", "#....#", "#....#", "######", "#....#", "#....#", "#....#", "#....#"),
    "I": (".####.", "..##..", "..##..", "..##..", "..##..", "..##..", "..##..", ".####."),
    "J": ("..####", "....#.", "....#.", "....#.", "....#.", "....#.", "#...#.", ".###.."),
    "K": ("#....#", "#...#.", "#..#..", "###...", "#..#..", "#...#.", "#....#", "#....#"),
    "L": ("#.....", "#.....", "#.....", "#.....", "#.....", "#.....", "#.....", "######"),
    "M": ("#....#", "##..##", "#.##.#", "#.##.#", "#....#", "#....#", "#....#", "#....#"),
    "N": ("#....#", "##...#", "#.#..#", "#..#.#", "#...##", "#....#", "#....#", "#....#"),
    "O": (".####.", "#....#", "#....#", "#....#", "#....#", "#....#", "#....#", ".####."),
    "P": ("#####.", "#....#", "#....#", "#####.", "#.....", "#.....", "#.....", "#....."),
    "Q": (".####.", "#....#", "#....#", "#....#", "#....#", "#.#..#", "#..#.#", ".##.##"),
    "R": ("#####.", "#....#", "#....#", "#####.", "#..#..", "#...#.", "#....#", "#....#"),
    "S": (".#####", "#.....", "#.....", ".####.", ".....#", ".....#", ".....#", "#####."),
    "T": ("######", "..##..", "..##..", "..##..", "..##..", "..##..", "..##..", "..##.."),
    "U": ("#....#", "#....#", "#....#", "#....#", "#....#", "#....#", "#....#", ".####."),
    "V": ("#....#", "#....#", "#....#", "#....#", "#....#", "#....#", ".#..#.", "..##.."),
    "W": ("#....#", "#....#", "#....#", "#....#", "#.##.#", "#.##.#", "##..##", "#....#"),
    "X": ("#....#", ".#..#.", "..##..", "..##..", "..##..", ".#..#.", "#....#", "#....#"),
    "Y": ("#....#", "#....#", ".#..#.", "..##..", "..##..", "..##..", "..##..", "..##.."),
    "Z": ("######", ".....#", "....#.", "...#..", "..#...", ".#....", "#.....", "######"),
    "0": (".####.", "#...##", "#..#.#", "#.#..#", "##...#", "#....#", "#....#", ".####."),
    "1": ("..##..", ".###..", "..##..", "..##..", "..##..", "..##..", "..##..", ".####."),
    "2": (".####.", "#....#", ".....#", "....#.", "...#..", "..#...", ".#....", "######"),
    "3": (".####.", "#....#", ".....#", "..###.", ".....#", ".....#", "#....#", ".####."),
    "4": ("...##.", "..#.#.", ".#..#.", "#...#.", "######", "....#.", "....#.", "....#."),
    "5": ("######", "#.....", "#.....", "#####.", ".....#", ".....#", "#....#", ".####."),
    "6": (".####.", "#....#", "#.....", "#####.", "#....#", "#....#", "#....#", ".####."),
    "7": ("######", ".....#", "....#.", "....#.", "...#..", "...#..", "..#...", "..#..."),
    "8": (".####.", "#....#", "#....#", ".####.", "#....#", "#....#", "#....#", ".####."),
    "9": (".####.", "#....#", "#....#", "#....#", ".#####", ".....#", "#....#", ".####."),
    " ": ("......", "......", "......", "......", "......", "......", "......", "......"),
    ".": ("......", "......", "......", "......", "......", "......", ".##...", ".##..."),
    ",": ("......", "......", "......", "......", "......", ".##...", ".##...", ".#...."),
    ":": ("......", ".##...", ".##...", "......", "......", ".##...", ".##...", "......"),
    ";": ("......", ".##...", ".##...", "......", "......", ".##...", ".##...", ".#...."),
    "'": ("..##..", "..##..", "..#...", "......", "......", "......", "......", "......"),
    "-": ("......", "......", "......", ".####.", "......", "......", "......", "......"),
    "+": ("......", "..##..", "..##..", ".####.", ".####.", "..##..", "..##..", "......"),
    "%": ("##...#", "##..#.", "....#.", "...#..", "..#...", ".#....", ".#..##", "#...##"),
    "/": (".....#", ".....#", "....#.", "....#.", "...#..", "..#...", "..#...", ".#...."),
    "(": ("..##..", ".#....", "#.....", "#.....", "#.....", "#.....", ".#....", "..##.."),
    ")": ("..##..", "....#.", ".....#", ".....#", ".....#", ".....#", "....#.", "..##.."),
    "!": ("..##..", "..##..", "..##..", "..##..", "..##..", "..##..", "......", "..##.."),
    "?": (".####.", "#....#", ".....#", "....#.", "...#..", "..##..", "......", "..##.."),
    "$": ("..##..", ".#####", "#.##.#", "#.##..", "..####", "...##.", "#.##.#", ".###.."),
    "&": (".###..", "#...#.", "#...#.", "..#...", ".#.#.#", "#..#..", "#...##", ".##.#."),
}

CELL_W = 6
CELL_H = 8


def glyph_rows(ch):
    return GLYPHS.get(ch, GLYPHS["?"])


def text_span(s, scale, tracking=1):
    """Pixel width of a string at the given integer scale."""
    if not s:
        return 0
    return len(s) * (CELL_W * scale + tracking) - tracking


def draw_text(cv, x, y, s, scale, color, tracking=1):
    """Paint a string with its top-left corner at (x, y); return end x."""
    pen = x
    for ch in s.upper():
        rows = glyph_rows(ch)
        for ry, row in enumerate(rows):
            for rx, cell in enumerate(row):
                if cell == "#":
                    cv.block(pen + rx * scale, y + ry * scale, scale, scale, color)
        pen += CELL_W * scale + tracking
    return pen


def centered(cv, cx, y, s, scale, color, tracking=1):
    draw_text(cv, cx - text_span(s, scale, tracking) // 2, y, s, scale, color, tracking)


def wrap_words(s, scale, max_px, tracking=1):
    """Greedy word wrap against a pixel budget; returns a list of lines."""
    lines, cur = [], ""
    for word in s.split():
        trial = word if not cur else cur + " " + word
        if text_span(trial, scale, tracking) <= max_px or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def paragraph(cv, x, y, s, scale, color, max_px, leading):
    """Paint a wrapped paragraph; return the y just below it."""
    for line in wrap_words(s, scale, max_px):
        draw_text(cv, x, y, line, scale, color)
        y += leading
    return y


# ---------------------------------------------------------------------------
# Canvas: a flat RGB buffer plus a small kit of drawing primitives.
# ---------------------------------------------------------------------------

class Canvas:
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.buf = bytearray(bytes(bg) * (w * h))

    def put(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.buf[i:i + 3] = bytes(color)

    def block(self, x, y, w, h, color):
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        run = bytes(color) * (x1 - x0)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.buf[i:i + len(run)] = run

    def frame(self, x, y, w, h, color, thick=2):
        self.block(x, y, w, thick, color)
        self.block(x, y + h - thick, w, thick, color)
        self.block(x, y, thick, h, color)
        self.block(x + w - thick, y, thick, h, color)

    def segment(self, x0, y0, x1, y1, color, thick=2):
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        r = thick // 2
        for t in range(steps + 1):
            x = x0 + (x1 - x0) * t // steps
            y = y0 + (y1 - y0) * t // steps
            self.block(x - r, y - r, thick, thick, color)

    def dotted_arc(self, x0, y0, xc, yc, x1, y1, color, dash=7):
        """Quadratic bezier traced as dashes from (x0,y0) to (x1,y1)."""
        for t in range(101):
            f = t / 100.0
            g = 1.0 - f
            x = int(g * g * x0 + 2 * g * f * xc + f * f * x1)
            y = int(g * g * y0 + 2 * g * f * yc + f * f * y1)
            if (t // dash) % 2 == 0:
                self.block(x - 1, y - 1, 3, 3, color)

    def disc(self, cx, cy, r, color):
        for dy in range(-r, r + 1):
            span = int((r * r - dy * dy) ** 0.5)
            self.block(cx - span, cy + dy, 2 * span + 1, 1, color)

    def burst(self, cx, cy, r, color):
        """Eight-ray explosion star."""
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1),
                       (1, 1), (1, -1), (-1, 1), (-1, -1)):
            self.segment(cx, cy, cx + dx * r, cy + dy * r, color, 3)
        self.disc(cx, cy, 4, color)

    def plume(self, x, y, puffs, color):
        """Rising smoke: a column of growing, drifting discs."""
        for i, (r, dx) in enumerate(puffs):
            self.disc(x + dx, y - i * (r + 4), r, color)


# ---------------------------------------------------------------------------
# Scene painters.  Each receives the canvas and a box (x, y, w, h).
# ---------------------------------------------------------------------------

def scene_missiles(cv, x, y, w, h):
    ground = y + h - 16
    cv.segment(x + 4, ground, x + w - 4, ground, INK, 3)
    for gx in range(x + 14, x + w - 10, 26):          # crop rows on the field
        cv.segment(gx, ground, gx, ground - 7, GREEN, 2)
    for hx in (x + 90, x + w - 150):                   # two farmhouses
        cv.block(hx, ground - 20, 34, 20, INK)
        cv.segment(hx - 4, ground - 20, hx + 17, ground - 32, RED, 3)
        cv.segment(hx + 17, ground - 32, hx + 38, ground - 20, RED, 3)
    strikes = [(x + int(w * 0.52), ground - 4),
               (x + int(w * 0.74), ground - 4),
               (x + int(w * 0.90), ground - 4)]
    starts = [(x + 26, y + 8), (x + 130, y + 2), (x + 250, y + 12)]
    for (sx, sy), (tx, ty) in zip(starts, strikes):
        cv.dotted_arc(sx, sy, (sx + tx) // 2, y - 26, tx, ty, RED)
        cv.burst(tx, ty - 2, 13, ORANGE)
        cv.burst(tx, ty - 2, 7, RED)
    draw_text(cv, x + 30, y + h - 40, "KH-101", 1, FAINT)
    draw_text(cv, x + w - 120, y + 6, "RZESZOW", 1, FAINT)


def scene_selloff(cv, x, y, w, h):
    base = y + h - 14
    cv.segment(x + 8, y + 8, x + 8, base, FAINT, 2)
    cv.segment(x + 8, base, x + w - 6, base, FAINT, 2)
    pts = [(x + 12, y + 16), (x + 34, y + 22), (x + 52, y + 18),
           (x + 70, y + 34), (x + 88, y + 52), (x + 104, y + 78),
           (x + w - 10, base - 6)]
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        cv.segment(ax, ay, bx, by, RED, 3)
    tipx, tipy = pts[-1]
    cv.segment(tipx, tipy, tipx - 12, tipy - 2, RED, 3)
    cv.segment(tipx, tipy, tipx - 3, tipy - 12, RED, 3)
    draw_text(cv, x + 16, y + h - 34, "-3.7%", 2, RED)


def scene_port(cv, x, y, w, h):
    water = y + h - 12
    cv.segment(x + 4, water, x + w - 4, water, NAVY, 3)
    mast = x + 26
    cv.block(mast, y + 14, 5, water - y - 14, INK)                 # crane mast
    cv.segment(mast, y + 14, x + w - 18, y + 14, INK, 4)          # crane jib
    cv.segment(x + w - 34, y + 14, x + w - 34, y + 40, INK, 2)    # cable
    cv.frame(x + w - 46, y + 40, 24, 16, GOLD, 3)                 # container
    hull_y = water - 16
    cv.block(x + 44, hull_y, w - 70, 10, RED)                     # ship hull
    cv.block(x + 58, hull_y - 10, 30, 10, INK)                    # bridge block
    cv.plume(x + 112, hull_y - 6, [(5, 0), (7, 4), (9, 9)], SMOKE)


def scene_flags(cv, x, y, w, h):
    base = y + h - 10
    cv.segment(x + 6, base, x + w - 6, base, INK, 2)
    for px, kind in ((x + 30, "uk"), (x + w - 52, "eu")):
        cv.block(px, y + 12, 4, base - y - 12, INK)
        fx, fy, fw, fh = px + 4, y + 12, 40, 26
        if kind == "uk":
            cv.block(fx, fy, fw, fh, NAVY)
            cv.block(fx + fw // 2 - 3, fy, 6, fh, WHITE)
            cv.block(fx, fy + fh // 2 - 3, fw, 6, WHITE)
            cv.block(fx + fw // 2 - 2, fy, 4, fh, RED)
            cv.block(fx, fy + fh // 2 - 2, fw, 4, RED)
        else:
            cv.block(fx, fy, fw, fh, NAVY)
            for k in range(8):
                ang = k * 3.14159 / 4
                sx = fx + fw // 2 + int(9 * _cos(ang))
                sy = fy + fh // 2 + int(8 * _sin(ang))
                cv.block(sx, sy, 2, 2, GOLD)
    cv.segment(x + w // 2 - 14, y + h - 34, x + w // 2 - 4, y + h - 22, GREEN, 4)
    cv.segment(x + w // 2 - 4, y + h - 22, x + w // 2 + 16, y + h - 44, GREEN, 4)


def _cos(a):
    return _trig(a, True)


def _sin(a):
    return _trig(a, False)


def _trig(a, want_cos):
    """Tiny Taylor trig so the flag stars need no imports beyond basics."""
    while a > 3.14159:
        a -= 2 * 3.14159
    if not want_cos:
        a = 1.57079 - a
        while a > 3.14159:
            a -= 2 * 3.14159
    term, total, n = 1.0, 1.0, 1
    while n <= 10:
        term *= -a * a / ((2 * n - 1) * (2 * n))
        total += term
        n += 1
    return total


def scene_tanker(cv, x, y, w, h):
    water = y + h - 12
    cv.segment(x + 4, water, x + w - 4, water, NAVY, 3)
    hull_y = water - 14
    cv.block(x + 14, hull_y, w - 28, 9, INK)
    cv.block(x + 22, hull_y - 8, w - 60, 8, FAINT)
    cv.block(x + w - 34, hull_y - 20, 12, 20, INK)
    fx, fy = x + 52, hull_y - 10                              # flame stack
    cv.disc(fx, fy - 16, 5, GOLD)
    cv.disc(fx, fy - 9, 8, ORANGE)
    cv.disc(fx, fy - 2, 10, RED)
    cv.plume(fx + 6, fy - 26, [(5, 2), (7, 6), (9, 11)], SMOKE)


SCENES = {
    "missiles": scene_missiles,
    "selloff": scene_selloff,
    "port": scene_port,
    "flags": scene_flags,
    "tanker": scene_tanker,
}

# ---------------------------------------------------------------------------
# The day's news, as reported on Saturday 21 November 2026 (Reuters, AP,
# The Times and wire roundups of the day).
# ---------------------------------------------------------------------------

PAGE = [
    {"kind": "masthead",
     "title": "THE SATURDAY LEDGER",
     "left": "VOL. I - NO. 21",
     "right": "WORLD EDITION",
     "date": "SATURDAY 21 NOVEMBER 2026"},
    {"kind": "hero",
     "kicker": "WAR IN EUROPE - NATO'S EASTERN FLANK",
     "headline": ["RUSSIAN MISSILES", "LAND IN POLAND"],
     "dek": ("TWO MISSILES AND A JET DRONE FELL ON NATO SOIL DURING ONE OF "
             "THE LARGEST STRIKES ON UKRAINE OF THE WAR. WARSAW CALLS IT A "
             "DELIBERATE PROVOCATION."),
     "scene": "missiles",
     "caption": ("A KH-101 CAME DOWN NEAR NOWY LIPOWIEC; TWO MORE OBJECTS FELL "
                 "NEAR RUDNIK AND MOLODYCZ. NO ONE IN POLAND WAS HURT.")},
    {"kind": "cards",
     "cards": [
         {"accent": RED, "scene": "selloff",
          "kicker": "MARKETS",
          "headline": "WALL STREET IN CORRECTION",
          "body": ("S+P 500 FELL 3.7 PCT, NASDAQ 5.3 PCT AS THE AI SELLOFF "
                   "DEEPENED. NVIDIA -14 PCT; NIKKEI -5 PCT.")},
         {"accent": NAVY, "scene": "port",
          "kicker": "MIDDLE EAST",
          "headline": "41 DEAD IN HODEIDAH STRIKE",
          "body": ("HOUTHIS REPORT 41 KILLED AS COALITION JETS HIT YEMEN'S "
                   "PORT. THREE MISSILES DOWNED OVER RIYADH.")},
         {"accent": GREEN, "scene": "flags",
          "kicker": "BRUSSELS",
          "headline": "FOOD CHECKS SCRAPPED",
          "body": ("LONDON AND BRUSSELS END FOOD CHECKS, PENDING A FEES "
                   "DEAL, AND ADD A YOUTH SCHEME FOR UNDER-30S.")},
         {"accent": ORANGE, "scene": "tanker",
          "kicker": "GULF OF OMAN",
          "headline": "TANKER ABLAZE OFF OMAN",
          "body": ("A TANKER CAUGHT FIRE OFF KHASAB. UKMTO BLAMES A "
                   "PROJECTILE; IRAN'S GUARDS SAY A MINE. CREW SAFE.")},
     ]},
    {"kind": "briefs",
     "label": "IN BRIEF",
     "lines": [
         "ESTONIA SHUTS FIVE RUSSIA ROAD CROSSINGS FROM 1 DECEMBER",
         "INDONESIA AND CHINA SIGN $15BN OF DEALS IN SHENZHEN TALKS",
         "MLAMBO-NGCUKA DIES AT 71 +++ 3 SALVADORAN SOLDIERS DIE IN HAITI",
     ]},
    {"kind": "footer",
     "text": "SATURDAY 21 NOVEMBER 2026 - DRAWN BY AN AI AGENT FOR MAKE.FUN"},
]


# ---------------------------------------------------------------------------
# Section painters.  Each returns the height it consumed.
# ---------------------------------------------------------------------------

def paint_masthead(cv, sec, top):
    cv.block(MARGIN, top, COL_W, 5, INK)
    cv.block(MARGIN, top + 8, COL_W, 2, INK)
    draw_text(cv, MARGIN, top + 22, sec["left"], 2, FAINT)
    rspan = text_span(sec["right"], 2)
    draw_text(cv, PAGE_W - MARGIN - rspan, top + 22, sec["right"], 2, FAINT)
    centered(cv, PAGE_W // 2, top + 16, sec["date"], 3, RED)
    centered(cv, PAGE_W // 2, top + 44, sec["title"], 6, INK)
    cv.block(MARGIN, top + 96, COL_W, 3, INK)
    return 104


def paint_hero(cv, sec, top):
    draw_text(cv, MARGIN, top, sec["kicker"], 2, RED)
    y = top + 26
    for line in sec["headline"]:
        draw_text(cv, MARGIN, y, line, 6, INK)
        y += 56
    y = paragraph(cv, MARGIN, y + 4, sec["dek"], 2, INK, COL_W, 19)
    scene_y = y + 6
    SCENES[sec["scene"]](cv, MARGIN, scene_y, COL_W, 120)
    y = scene_y + 128
    y = paragraph(cv, MARGIN, y, sec["caption"], 2, FAINT, COL_W, 19)
    return y - top


def paint_cards(cv, sec, top):
    gap = 16
    card_w = (COL_W - gap) // 2
    card_h = 190
    y = top
    for row in range(2):
        for col in range(2):
            card = sec["cards"][row * 2 + col]
            x = MARGIN + col * (card_w + gap)
            paint_card(cv, card, x, y, card_w, card_h)
        y += card_h + 12
    return y - top - 12


def paint_card(cv, card, x, y, w, h):
    cv.frame(x, y, w, h, INK, 2)
    cv.block(x, y, w, 6, card["accent"])
    sx, sy, sw, sh = x + 12, y + 40, 120, 128
    SCENES[card["scene"]](cv, sx, sy, sw, sh)
    tx = x + 146
    tw = x + w - 12 - tx
    draw_text(cv, tx, y + 14, card["kicker"], 2, card["accent"])
    hy = paragraph(cv, tx, y + 38, card["headline"], 3, INK, tw, 27)
    paragraph(cv, tx, hy + 4, card["body"], 2, INK, tw, 18)


def paint_briefs(cv, sec, top):
    cv.block(MARGIN, top, COL_W, 60, INK)
    cv.block(MARGIN + 10, top + 10, 96, 40, RED)
    centered(cv, MARGIN + 58, top + 15, "IN", 2, WHITE)
    centered(cv, MARGIN + 58, top + 33, "BRIEF", 2, WHITE)
    y = top + 5
    for line in sec["lines"]:
        draw_text(cv, MARGIN + 122, y, line, 2, WHITE)
        y += 18
    return 68


def paint_footer(cv, sec, top):
    centered(cv, PAGE_W // 2, top + 2, sec["text"], 2, FAINT)
    return 20


PAINTERS = {
    "masthead": paint_masthead,
    "hero": paint_hero,
    "cards": paint_cards,
    "briefs": paint_briefs,
    "footer": paint_footer,
}


def compose():
    cv = Canvas(PAGE_W, PAGE_H, PAPER)
    y = 22
    for sec in PAGE:
        y += PAINTERS[sec["kind"]](cv, sec, y) + 10
    return cv


# ---------------------------------------------------------------------------
# PNG writer: signature, IHDR, one IDAT of filter-0 scanlines, IEND.
# ---------------------------------------------------------------------------

def chunk(tag, payload):
    body = tag + payload
    return (struct.pack(">I", len(payload)) + body
            + struct.pack(">I", binascii.crc32(body) & 0xFFFFFFFF))


def encode_png(cv):
    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    raw = bytearray()
    stride = cv.w * 3
    for yy in range(cv.h):
        raw.append(0)
        raw += cv.buf[yy * stride:(yy + 1) * stride]
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    data = encode_png(compose())
    with open(os.path.join(out_dir, "entry.png"), "wb") as fh:
        fh.write(data)


if __name__ == "__main__":
    main()
