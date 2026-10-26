"""Builds the SVG assets of the profile README.

    python scripts/build_assets.py

Everything is drawn here: a 5x5 pixel font, small sprites and the layouts.
No web fonts, no scripts and no third-party image services, so GitHub can
serve the files as they are. Edit the content lists (ABOUT, PROJECTS,
QUESTS, INVENTORY...) and run it again.

Each unsuffixed SVG is the dark version. write() also emits its -light.svg
counterpart from LIGHT_COLORS; README <picture> sources select the browser's
color scheme. Keep every foreground/background pair in that palette mapping.
The stack and certification panels are separate 400px images so they can
wrap on mobile. Technology logos are vendored in icons.json (Simple Icons,
CC0); missing logos and abstract concepts use explicit text abbreviations.
"""

from __future__ import annotations

import functools
import json
import re
from pathlib import Path

from PIL import ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SCRIPTS = ROOT / "scripts"

# Same palette as the portfolio.
BG = "#0c0d0b"
BG2 = "#131512"
LINE = "#2c2e29"
INK = "#eceee6"
INK2 = "#c9ccc1"
MUTED = "#8d9288"
ACCENT = "#5ce483"
ACCENT_DIM = "#2a6b3d"

# The default assets retain the original dark palette. The light counterparts
# share the exact same geometry and motion, with explicit semantic color pairs.
LIGHT_COLORS = {
    BG: "#f8faf8",
    BG2: "#eef4ef",
    LINE: "#b8c8bc",
    INK: "#17261c",
    INK2: "#344b3b",
    MUTED: "#526858",
    ACCENT: "#1c763a",
    ACCENT_DIM: "#c1d8c7",
    "#b6f7c8": "#115b2b",  # Header's animated highlight.
}

SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"

REDUCED_MOTION = "@media (prefers-reduced-motion: reduce) { * { animation: none !important; } }"


# --------------------------------------------------------------------------
# Pixel font: 5 rows high, uppercase only.
# --------------------------------------------------------------------------

FONT = {
    "A": [".##.", "#..#", "####", "#..#", "#..#"],
    "B": ["###.", "#..#", "###.", "#..#", "###."],
    "C": [".###", "#...", "#...", "#...", ".###"],
    "D": ["###.", "#..#", "#..#", "#..#", "###."],
    "E": ["####", "#...", "###.", "#...", "####"],
    "F": ["####", "#...", "###.", "#...", "#..."],
    "G": [".###", "#...", "#.##", "#..#", ".###"],
    "H": ["#..#", "#..#", "####", "#..#", "#..#"],
    "I": ["###", ".#.", ".#.", ".#.", "###"],
    "J": ["...#", "...#", "...#", "#..#", ".##."],
    "K": ["#..#", "#.#.", "##..", "#.#.", "#..#"],
    "L": ["#...", "#...", "#...", "#...", "####"],
    "M": ["#...#", "##.##", "#.#.#", "#...#", "#...#"],
    "N": ["#..#", "##.#", "#.##", "#..#", "#..#"],
    "O": [".##.", "#..#", "#..#", "#..#", ".##."],
    "P": ["###.", "#..#", "###.", "#...", "#..."],
    "Q": [".##.", "#..#", "#..#", "#.#.", ".#.#"],
    "R": ["###.", "#..#", "###.", "#.#.", "#..#"],
    "S": [".###", "#...", ".##.", "...#", "###."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#.."],
    "U": ["#..#", "#..#", "#..#", "#..#", ".##."],
    "V": ["#...#", "#...#", "#...#", ".#.#.", "..#.."],
    "W": ["#...#", "#...#", "#.#.#", "##.##", "#...#"],
    "X": ["#..#", "#..#", ".##.", "#..#", "#..#"],
    "Y": ["#...#", ".#.#.", "..#..", "..#..", "..#.."],
    "Z": ["####", "...#", ".##.", "#...", "####"],
    "0": [".##.", "#..#", "#..#", "#..#", ".##."],
    "1": [".#.", "##.", ".#.", ".#.", "###"],
    "2": ["###.", "...#", ".##.", "#...", "####"],
    "3": ["###.", "...#", ".##.", "...#", "###."],
    "4": ["#..#", "#..#", "####", "...#", "...#"],
    "5": ["####", "#...", "###.", "...#", "###."],
    "6": [".##.", "#...", "###.", "#..#", ".##."],
    "7": ["####", "...#", "..#.", ".#..", ".#.."],
    "8": [".##.", "#..#", ".##.", "#..#", ".##."],
    "9": [".##.", "#..#", ".###", "...#", ".##."],
    ".": [".", ".", ".", ".", "#"],
    ",": [".", ".", ".", "#", "#"],
    ":": [".", "#", ".", "#", "."],
    "!": ["#", "#", "#", ".", "#"],
    "'": ["#", "#", ".", ".", "."],
    "·": [".", ".", "#", ".", "."],
    "-": ["...", "...", "###", "...", "..."],
    "+": ["...", ".#.", "###", ".#.", "..."],
    "/": ["..#", "..#", ".#.", "#..", "#.."],
    ">": ["#..", ".#.", "..#", ".#.", "#.."],
    "&": [".#..", "#.#.", ".#.#", "#.#.", ".#.#"],
    "?": ["###.", "...#", ".##.", "....", ".#.."],
    "▶": ["#...", "##..", "###.", "##..", "#..."],
    "(": [".#", "#.", "#.", "#.", ".#"],
    ")": ["#.", ".#", ".#", ".#", "#."],
    " ": ["..", "..", "..", "..", ".."],
}


def glyph(ch: str) -> list[str]:
    try:
        return FONT[ch.upper()]
    except KeyError:
        raise ValueError(f"no glyph for {ch!r}") from None


def char_advances(text: str) -> list[int]:
    """Left edge of each character, in font units."""
    out, x = [], 0
    for ch in text:
        out.append(x)
        x += len(glyph(ch)[0]) + 1
    return out


def text_width(text: str) -> int:
    if not text:
        return 0
    return sum(len(glyph(ch)[0]) + 1 for ch in text) - 1


def pixel_text(text: str, x: float, y: float, unit: float, fill: str) -> str:
    """Text as rects, merging the horizontal runs of every glyph row."""
    rects = []
    for ch, cx in zip(text, char_advances(text)):
        for row, line in enumerate(glyph(ch)):
            col = 0
            while col < len(line):
                if line[col] == "#":
                    start = col
                    while col < len(line) and line[col] == "#":
                        col += 1
                    rects.append(
                        f'<rect x="{fmt(x + (cx + start) * unit)}" y="{fmt(y + row * unit)}" '
                        f'width="{fmt((col - start) * unit)}" height="{fmt(unit)}"/>'
                    )
                else:
                    col += 1
    return f'<g fill="{fill}">{"".join(rects)}</g>'


def pixel_blocks(text: str, x: float, y: float, unit: float):
    """One (x, y, char_index, row, col) per lit pixel, for per-block animation."""
    for i, (ch, cx) in enumerate(zip(text, char_advances(text))):
        for row, line in enumerate(glyph(ch)):
            for col, cell in enumerate(line):
                if cell == "#":
                    yield x + (cx + col) * unit, y + row * unit, i, row, col


def fmt(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def svg(width: int, height: int, body: str, title: str, style: str = "") -> str:
    css = f"<style>{style}{REDUCED_MOTION}</style>" if style else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">'
        f"<title>{esc(title)}</title>{css}{body}</svg>\n"
    )


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    print(f"{path.relative_to(ROOT)}  {len(content.encode()) / 1024:.1f} KB")
    if path.suffix == ".svg" and not path.stem.endswith(("-dark", "-light")):
        light = re.sub(r"#[0-9a-fA-F]{6}\b", lambda m: LIGHT_COLORS.get(m[0].lower(), m[0]), content)
        write(path.with_stem(path.stem + "-light"), light)


def pseudo_random(*keys: int) -> float:
    """Deterministic 0..1, so rebuilding gives byte-identical files."""
    h = 2166136261
    for k in keys:
        h = ((h ^ (k & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    return (h % 10000) / 10000


# --------------------------------------------------------------------------
# Sprites: 12x12, two frames that alternate.
# --------------------------------------------------------------------------

SPRITE_COLORS = {"g": ACCENT, "d": ACCENT_DIM, "w": INK, "m": MUTED, "k": LINE}

SPRITES = {
    # Invoice that gets stamped.
    "invoice": (
        [
            "..wwwwwwww..",
            "..wwwwwwww..",
            "..wkkkkkkw..",
            "..wwwwwwww..",
            "..wkkkkwww..",
            "..wwwwwwww..",
            "..wkkkkkkw..",
            "..wwwwwwww..",
            "..wkkkwwww..",
            "..wwwwwwww..",
            "..wwwwwwww..",
            "..ww.ww.ww..",
        ],
        [
            "..wwwwwwww..",
            "..wwwwwwww..",
            "..wkkkkkkw..",
            "..wwwwwwww.g",
            "..wkkkkwwwgg",
            "..wwwwwwwgg.",
            "..wgwkkkgg..",
            "..wggwwgg...",
            "..wkgggg....",
            "..wwwggw....",
            "..wwwwwwww..",
            "..ww.ww.ww..",
        ],
    ),
    # Checkered cab; the roof light and the headlight blink.
    "taxi": (
        [
            "............",
            "............",
            "....dddd....",
            "...wwwwww...",
            "..wkkwwkkw..",
            "..wkkwwkkw..",
            "wwwwwwwwwwww",
            "wkwkwkwkwkww",
            "wwwwwwwwwwww",
            ".mmm....mmm.",
            ".mkm....mkm.",
            "..m......m..",
        ],
        [
            "............",
            "............",
            "....gggg....",
            "...wwwwww...",
            "..wkkwwkkw..",
            "..wkkwwkkw..",
            "wwwwwwwwwwwg",
            "wkwkwkwkwkwg",
            "wwwwwwwwwwww",
            ".mmm....mmm.",
            ".mkm....mkm.",
            "..m......m..",
        ],
    ),
    # Plane climbing with a contrail.
    "plane": (
        [
            ".....ww.....",
            ".....ww.....",
            ".....ww.....",
            "....wwww....",
            "..wwwwwwww..",
            "wwwwwwwwwwww",
            ".....ww.....",
            ".....ww.....",
            "....wwww....",
            "...wwwwww...",
            "............",
            ".....d......",
        ],
        [
            ".....ww.....",
            ".....ww.....",
            "....wwww....",
            "..wwwwwwww..",
            "wwwwwwwwwwww",
            ".....ww.....",
            ".....ww.....",
            "....wwww....",
            "...wwwwww...",
            "............",
            "......d.....",
            "....d.......",
        ],
    ),
    # Watchtower sweeping its light ("atalaya" means watchtower).
    "tower": (
        [
            "............",
            ".....ww.....",
            "....wwww....",
            "...wwwwww...",
            "ddd.wggw....",
            "dd..wwww....",
            "....w..w....",
            "....w..w....",
            "...ww..ww...",
            "...w.ww.w...",
            "..w..ww..w..",
            ".ww......ww.",
        ],
        [
            "............",
            ".....ww.....",
            "....wwww....",
            "...wwwwww...",
            "....wggw.ddd",
            "....wwww..dd",
            "....w..w....",
            "....w..w....",
            "...ww..ww...",
            "...w.ww.w...",
            "..w..ww..w..",
            ".ww......ww.",
        ],
    ),
    # Ranking that changes with the measure.
    "chart": (
        [
            "............",
            "............",
            "....ww......",
            "....ww......",
            "....ww......",
            "....ww.gg...",
            "....ww.gg...",
            ".gg.ww.gg...",
            ".gg.ww.gg...",
            ".gg.ww.gg.gg",
            ".gg.ww.gg.gg",
            "mmmmmmmmmmmm",
        ],
        [
            "............",
            "............",
            ".......ww...",
            ".......ww...",
            ".gg....ww...",
            ".gg....ww...",
            ".gg....ww.gg",
            ".gg....ww.gg",
            ".gg.gg.ww.gg",
            ".gg.gg.ww.gg",
            ".gg.gg.ww.gg",
            "mmmmmmmmmmmm",
        ],
    ),
    # Gamepad pressing its buttons.
    "gamepad": (
        [
            "............",
            "............",
            "............",
            "..wwwwwwww..",
            ".wwkwwwwwwg.",
            "wwkkkwwwdwww",
            "wwwkwwwwwwww",
            "wwwwwwwwwwww",
            "www......www",
            "ww........ww",
            "............",
            "............",
        ],
        [
            "............",
            "............",
            "............",
            "..wwwwwwww..",
            ".wwkwwwwwwd.",
            "wwkkkwwwgwww",
            "wwwkwwwwwwww",
            "wwwwwwwwwwww",
            "www......www",
            "ww........ww",
            "............",
            "............",
        ],
    ),
    # Play button for the live demos.
    "play": (
        [
            "............",
            "...g........",
            "...ggg......",
            "...ggggg....",
            "...ggggggg..",
            "...gggggggg.",
            "...ggggggg..",
            "...ggggg....",
            "...ggg......",
            "...g........",
            "............",
            "............",
        ],
        [
            "............",
            "...d........",
            "...ddd......",
            "...ddddd....",
            "...ddddddd..",
            "...dddddddd.",
            "...ddddddd..",
            "...ddddd....",
            "...ddd......",
            "...d........",
            "............",
            "............",
        ],
    ),
    # Car with a LiDAR pulsing (KITTI).
    "lidar": (
        [
            ".d...d...d..",
            "..d..d..d...",
            "...d.d.d....",
            "....ddd.....",
            ".....g......",
            "...wwwww....",
            "..wkkwkkw...",
            ".wwwwwwwwww.",
            ".wwwwwwwwww.",
            "..mm....mm..",
            "..mm....mm..",
            "............",
        ],
        [
            ".g...g...g..",
            "..g..g..g...",
            "...g.g.g....",
            "....ggg.....",
            ".....w......",
            "...wwwww....",
            "..wkkwkkw...",
            ".wwwwwwwwww.",
            ".wwwwwwwwww.",
            "..mm....mm..",
            "..mm....mm..",
            "............",
        ],
    ),
    # Brain with a spot that gets detected (BraTS).
    "brain": (
        [
            "............",
            "...wwwwww...",
            "..wmmwmmmw..",
            ".wmmwmmwmmw.",
            ".wmwmmwmmmw.",
            ".wmmmwmmmmw.",
            ".wmwmmmwmmw.",
            "..wmmwmmmw..",
            "...wwwwww...",
            ".....ww.....",
            ".....ww.....",
            "............",
        ],
        [
            "............",
            "...wwwwww...",
            "..wmmwmmmw..",
            ".wmmwmgggmw.",
            ".wmwmmgmgmw.",
            ".wmmmwgggmw.",
            ".wmwmmmwmmw.",
            "..wmmwmmmw..",
            "...wwwwww...",
            ".....ww.....",
            ".....ww.....",
            "............",
        ],
    ),
    # Open hand with landmarks, then a fist (gesture recognition).
    "hand": (
        [
            "...g.g.g....",
            "...w.w.w.g..",
            "...w.w.w.w..",
            ".g.w.w.w.w..",
            ".wwwwwwwww..",
            "..wwwwwwww..",
            "...wwwwwww..",
            "...wwwwww...",
            "....wwwww...",
            "....wwwww...",
            "............",
            "............",
        ],
        [
            "............",
            "............",
            "............",
            "...wwwwwww..",
            "..wwkwkwkw..",
            ".wwwwwwwww..",
            "..wwwwwwww..",
            "...wwwwww...",
            "....wwwww...",
            "....wwwww...",
            "............",
            "............",
        ],
    ),
    # Spinning poker chip.
    "chip": (
        [
            "....gwwg....",
            "..gggggggg..",
            ".gggddddggg.",
            ".ggd....dgg.",
            "ggd......dgg",
            "wgd......dgw",
            "wgd......dgw",
            "ggd......dgg",
            ".ggd....dgg.",
            ".gggddddggg.",
            "..gggggggg..",
            "....gwwg....",
        ],
        [
            "....gggg....",
            "..wwggggww..",
            ".gggddddggg.",
            ".ggd....dgg.",
            "ggd......dgg",
            "ggd......dgg",
            "ggd......dgg",
            "ggd......dgg",
            ".ggd....dgg.",
            ".gggddddggg.",
            "..wwggggww..",
            "....gggg....",
        ],
    ),
    # Wavelength dial: the needle swings into the target.
    "dial": (
        [
            "............",
            "............",
            "............",
            "...mmmmmm...",
            ".mm...gg.mm.",
            "m.w....ggg.m",
            "m..w.......m",
            "m...w......m",
            "m....ww....m",
            "mmmmmmmmmmmm",
            "............",
            "............",
        ],
        [
            "............",
            "............",
            "............",
            "...mmmmmm...",
            ".mm...gg.mm.",
            "m......gwg.m",
            "m......w...m",
            "m.....w....m",
            "m....ww....m",
            "mmmmmmmmmmmm",
            "............",
            "............",
        ],
    ),
    # Tabu cards: the word on the front card changes.
    "cards": (
        [
            ".....dddddd.",
            ".....dddddd.",
            ".wwwwwwdddd.",
            ".wgggwwdddd.",
            ".wwwwwwdddd.",
            ".wgggwwdddd.",
            ".wwwwwwdddd.",
            ".wggwwwdddd.",
            ".wwwwwwdddd.",
            ".wwwwww.....",
            ".wwwwww.....",
            "............",
        ],
        [
            ".....dddddd.",
            ".....dddddd.",
            ".wwwwwwdddd.",
            ".wggwwwdddd.",
            ".wwwwwwdddd.",
            ".wggggwdddd.",
            ".wwwwwwdddd.",
            ".wgwwwwdddd.",
            ".wwwwwwdddd.",
            ".wwwwww.....",
            ".wwwwww.....",
            "............",
        ],
    ),
    # Die rolling from three to five.
    "dice": (
        [
            "............",
            ".wwwwwwwwww.",
            ".wkkwwwwwww.",
            ".wkkwwwwwww.",
            ".wwwwwwwwww.",
            ".wwwwkkwwww.",
            ".wwwwkkwwww.",
            ".wwwwwwwwww.",
            ".wwwwwwwkkw.",
            ".wwwwwwwkkw.",
            ".wwwwwwwwww.",
            "............",
        ],
        [
            "............",
            ".wwwwwwwwww.",
            ".wkkwwwwkkw.",
            ".wkkwwwwkkw.",
            ".wwwwwwwwww.",
            ".wwwwkkwwww.",
            ".wwwwkkwwww.",
            ".wwwwwwwwww.",
            ".wkkwwwwkkw.",
            ".wkkwwwwkkw.",
            ".wwwwwwwwww.",
            "............",
        ],
    ),
    # Medal that catches the light.
    "medal": (
        [
            "..dd....dd..",
            "...dd..dd...",
            "....dddd....",
            "....gggg....",
            "..gggggggg..",
            ".gggddddggg.",
            ".ggdggggdgg.",
            ".ggdggggdgg.",
            ".ggdggggdgg.",
            ".gggddddggg.",
            "..gggggggg..",
            "....gggg....",
        ],
        [
            "..dd....dd..",
            "...dd..dd.w.",
            "....dddd.www",
            "....gggg..w.",
            "..gwgggggg..",
            ".gwgddddggg.",
            ".ggdggggdgg.",
            ".ggdggggdgg.",
            ".ggdggggdgg.",
            ".gggddddggg.",
            "..gggggggg..",
            "....gggg....",
        ],
    ),
}

ICONS_12 = {
    "linkedin": [
        ".gggggggggg.",
        "gggggggggggg",
        "gg.ggggggggg",
        "gggggggggggg",
        "gg.g....gggg",
        "gg.g.ggg.ggg",
        "gg.g.ggg.ggg",
        "gg.g.ggg.ggg",
        "gg.g.ggg.ggg",
        "gg.g.ggg.ggg",
        "gggggggggggg",
        ".gggggggggg.",
    ],
    "email": [
        "............",
        "gggggggggggg",
        "gg........gg",
        "g.g......g.g",
        "g..g....g..g",
        "g...g..g...g",
        "g....gg....g",
        "g..........g",
        "g..........g",
        "gggggggggggg",
        "............",
        "............",
    ],
    "portfolio": [
        "............",
        "gggggggggggg",
        "g.d.d.d....g",
        "gggggggggggg",
        "g..........g",
        "g.gggg.....g",
        "g..........g",
        "g.gggggggg.g",
        "g.gggggg...g",
        "g..........g",
        "gggggggggggg",
        "............",
    ],
}


def sprite_rects(rows: list[str], x: float, y: float, unit: float) -> str:
    out = []
    for r, line in enumerate(rows):
        c = 0
        while c < len(line):
            ch = line[c]
            if ch == ".":
                c += 1
                continue
            start = c
            while c < len(line) and line[c] == ch:
                c += 1
            out.append(
                f'<rect x="{fmt(x + start * unit)}" y="{fmt(y + r * unit)}" '
                f'width="{fmt((c - start) * unit)}" height="{fmt(unit)}" fill="{SPRITE_COLORS[ch]}"/>'
            )
    return "".join(out)


SPRITE_CSS = (
    "@keyframes fa{0%{opacity:1}50%{opacity:0}}"
    "@keyframes fb{0%{opacity:0}50%{opacity:1}}"
    ".fa{animation:fa 1.2s step-end infinite}"
    ".fb{opacity:0;animation:fb 1.2s step-end infinite}"
)


def sprite(name: str, x: float, y: float, unit: float, delay: float = 0) -> tuple[str, str]:
    """Two-frame sprite. Returns (markup, css). A delay desyncs sprites that share a file."""
    a, b = SPRITES[name]
    st = f' style="animation-delay:-{delay:.2f}s"' if delay else ""
    markup = (
        f'<g class="fa"{st}>{sprite_rects(a, x, y, unit)}</g>'
        f'<g class="fb"{st}>{sprite_rects(b, x, y, unit)}</g>'
    )
    return markup, SPRITE_CSS


# --------------------------------------------------------------------------
# Header
# --------------------------------------------------------------------------

NAME = ["JAVIER", "SAGUAR"]
ROLE = "PLAYER 1 · DATA ENGINEER"
SUBTITLE = "Final-year Data Engineering student · ETSIT-UPM, Madrid"
TYPED_LINES = [
    "BIG DATA PROJECTS",
    "CYBERSECURITY AUDITS",
    "APPS, TOOLS AND GAMES, BUILT END TO END",
]
SKILL_BARS = ["DATA ENGINEERING", "CYBERSECURITY"]


def build_header() -> None:
    W, H = 960, 320
    pw, ph = W - 8, H - 8
    style = []
    body = []

    # Panel with a hard offset shadow and the portfolio's faint grid.
    body.append(
        '<defs>'
        f'<pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">'
        f'<path d="M32 0H0V32" fill="none" stroke="{LINE}" stroke-width="1"/></pattern>'
        '<radialGradient id="fade" cx="62%" cy="0%" r="75%">'
        '<stop offset="0" stop-color="#fff" stop-opacity=".55"/>'
        '<stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
        f'<mask id="m"><rect width="{pw}" height="{ph}" fill="url(#fade)"/></mask>'
        f'<clipPath id="inner"><rect x="2" y="2" width="{pw - 4}" height="{ph - 4}"/></clipPath>'
        '</defs>'
    )
    body.append(f'<rect x="8" y="8" width="{pw}" height="{ph}" fill="{ACCENT_DIM}"/>')
    body.append(f'<rect width="{pw}" height="{ph}" fill="{BG}" stroke="{LINE}" stroke-width="2"/>')
    body.append(f'<rect width="{pw}" height="{ph}" fill="url(#grid)" mask="url(#m)"/>')

    tx = 48
    body.append(pixel_text(ROLE, tx, 44, 3, ACCENT))

    # Name on one line, dropped in block by block.
    style.append("@keyframes drop{from{opacity:0;transform:translateY(-18px)}to{opacity:1;transform:none}}")
    style.append(".b{animation:drop .5s cubic-bezier(.16,1,.3,1) both}")
    unit = 12
    name = " ".join(NAME)
    assert tx + text_width(name) * unit < pw - 24, "name too wide for the header"
    blocks = []
    for bx, by, ci, row, col in pixel_blocks(name, tx, 78, unit):
        delay = 0.1 + ci * 0.06 + pseudo_random(ci, row, col) * 0.35
        blocks.append(
            f'<rect class="b" style="animation-delay:{delay:.2f}s" x="{fmt(bx)}" y="{fmt(by)}" '
            f'width="{unit}" height="{unit}"/>'
        )
    body.append(f'<g fill="{INK}">{"".join(blocks)}</g>')

    body.append(
        f'<text x="{tx}" y="184" fill="{INK2}" font-family="{SANS}" font-size="19">{esc(SUBTITLE)}</text>'
    )

    # Typed lines: a cover the colour of the panel slides off each line,
    # one character at a time, then slides back.
    tu = 4
    ty = 210
    prompt_w = (text_width(">") + 2) * tu
    body.append(pixel_text(">", tx, ty, tu, ACCENT))
    lx = tx + prompt_w
    type_s, hold_s, erase_s, gap_s = 0.075, 1.9, 0.03, 0.35
    windows = []
    t = 0.0
    for line in TYPED_LINES:
        n = len(line)
        start = t
        t += n * type_s + hold_s + n * erase_s + gap_s
        windows.append((start, t))
    total = t
    style.append(f"@keyframes blink{{0%{{opacity:1}}50%{{opacity:0}}}}")
    style.append(".cur{animation:blink 1s step-end infinite}")
    max_w = 0
    for li, line in enumerate(TYPED_LINES):
        width_units = text_width(line)
        max_w = max(max_w, width_units * tu)
        adv = char_advances(line) + [width_units + 1]
        start, end = windows[li]
        n = len(line)

        def pct(sec: float) -> str:
            return f"{100 * sec / total:.3f}%"

        frames = [f"0%{{transform:translateX(0)}}"]
        for k in range(1, n + 1):
            frames.append(f"{pct(start + k * type_s)}{{transform:translateX({adv[k] * tu}px)}}")
        erase_from = start + n * type_s + hold_s
        for k in range(n - 1, -1, -1):
            frames.append(
                f"{pct(erase_from + (n - k) * erase_s)}{{transform:translateX({adv[k] * tu}px)}}"
            )
        frames.append("100%{transform:translateX(0)}")
        style.append(f"@keyframes c{li}{{{''.join(frames)}}}")
        vis = [f"0%{{opacity:0}}", f"{pct(start)}{{opacity:1}}", f"{pct(end)}{{opacity:0}}", "100%{opacity:0}"]
        if start == 0:
            vis = ["0%{opacity:1}", f"{pct(end)}{{opacity:0}}", "100%{opacity:0}"]
        style.append(f"@keyframes v{li}{{{''.join(vis)}}}")
        style.append(f".l{li}{{animation:v{li} {total:.2f}s step-end infinite}}")
        style.append(f".c{li}{{animation:c{li} {total:.2f}s step-end infinite}}")

        # Without animation (reduced motion) the first line shows complete.
        base_vis = "" if li == 0 else ' opacity="0"'
        base_shift = (width_units + 1) * tu if li == 0 else 0
        cover_w = width_units * tu + 40
        body.append(
            f'<g class="l{li}"{base_vis} clip-path="url(#inner)">'
            f"{pixel_text(line, lx, ty, tu, INK)}"
            f'<g class="c{li}" style="transform:translateX({base_shift}px)">'
            f'<rect x="{lx}" y="{ty - 2}" width="{cover_w}" height="{5 * tu + 4}" fill="{BG}"/>'
            f'<rect class="cur" x="{lx}" y="{ty - 2}" width="{tu + 2}" height="{5 * tu + 4}" fill="{ACCENT}"/>'
            f"</g></g>"
        )
    assert lx + max_w < pw - 24, "typed line too long for the header"

    # Skill bars: they fill up, glow at the top for a few seconds, drop to
    # zero at once and start again.
    bars_y = 252
    pips, pip_w, pip_gap, pip_h = 20, 15, 4, 12
    step, hold, rest, first = 0.09, 3.0, 0.45, 0.4
    cycle = first + 0.2 + pips * step + 0.1 + hold + rest
    reset = cycle - rest
    bright = "#b6f7c8"

    def at(sec: float) -> str:
        return f"{100 * sec / cycle:.3f}%"

    body.append(
        '<defs><filter id="glow" x="-10%" y="-150%" width="120%" height="400%">'
        '<feGaussianBlur stdDeviation="5"/></filter></defs>'
    )
    for b, label in enumerate(SKILL_BARS):
        x = tx + b * 452
        start = first + b * 0.2
        full = start + pips * step + 0.1
        body.append(pixel_text(label, x, bars_y, 2, INK2))
        py = bars_y + 18
        bar_w = pips * (pip_w + pip_gap) - pip_gap
        glow = [
            "0%{opacity:0}", f"{at(full)}{{opacity:0}}", f"{at(full + 0.25)}{{opacity:.55}}",
            f"{at(full + 0.9)}{{opacity:.3}}", f"{at(full + 1.5)}{{opacity:.55}}",
            f"{at(full + 2.1)}{{opacity:.3}}", f"{at(reset - 0.02)}{{opacity:.5}}",
            f"{at(reset)}{{opacity:0}}", "100%{opacity:0}",
        ]
        style.append(f"@keyframes g{b}{{{''.join(glow)}}}.g{b}{{animation:g{b} {cycle:.2f}s linear infinite}}")
        body.append(
            f'<rect class="g{b}" opacity="0" x="{x}" y="{py}" width="{bar_w}" height="{pip_h}" '
            f'fill="{ACCENT}" filter="url(#glow)"/>'
        )
        for i in range(pips):
            frames = ["0%{fill:" + LINE + "}", f"{at(start + (i + 1) * step)}{{fill:{ACCENT}}}"]
            for k in range(3):
                shine = full + 0.3 + k * 0.9 + i * 0.025
                frames.append(f"{at(shine)}{{fill:{bright}}}")
                frames.append(f"{at(shine + 0.12)}{{fill:{ACCENT}}}")
            frames += [f"{at(reset)}{{fill:{LINE}}}", "100%{fill:" + LINE + "}"]
            style.append(
                f"@keyframes s{b}_{i}{{{''.join(frames)}}}"
                f".s{b}_{i}{{animation:s{b}_{i} {cycle:.2f}s step-end infinite}}"
            )
            # Base fill is the full bar, which is what reduced motion shows.
            body.append(
                f'<rect class="s{b}_{i}" x="{x + i * (pip_w + pip_gap)}" y="{py}" width="{pip_w}" '
                f'height="{pip_h}" fill="{ACCENT}"/>'
            )

    title = f"{' '.join(NAME).title()}. {SUBTITLE}."
    write(ASSETS / "header.svg", svg(W, H, "".join(body), title, "".join(style)))


# --------------------------------------------------------------------------
# Contact buttons
# --------------------------------------------------------------------------

BUTTONS = [("linkedin", "LINKEDIN"), ("email", "EMAIL"), ("portfolio", "PORTFOLIO")]


def build_buttons() -> None:
    W, H = 236, 64
    for key, label in BUTTONS:
        body = [
            f'<rect x="5" y="5" width="{W - 5}" height="{H - 5}" fill="{ACCENT_DIM}"/>',
            f'<rect x="1" y="1" width="{W - 7}" height="{H - 7}" fill="{BG2}" stroke="{ACCENT}" stroke-width="2"/>',
        ]
        icon_unit = 3
        ix, iy = 18, (H - 5 - 12 * icon_unit) / 2
        rows = ICONS_12[key]
        body.append(sprite_rects(rows, ix, iy, icon_unit))
        lw = text_width(label) * 3
        lx = ix + 12 * icon_unit + ((W - 7) - (ix + 12 * icon_unit) - lw) / 2
        body.append(pixel_text(label, lx, (H - 5 - 15) / 2, 3, INK))
        write(ASSETS / "buttons" / f"{key}.svg", svg(W, H, "".join(body), label.title()))


# --------------------------------------------------------------------------
# Project cards
# --------------------------------------------------------------------------

PROJECTS = [
    {
        "id": "albertitos",
        "sprite": "invoice",
        "name": "ALBERTITOS",
        "context": "HackSpain 2026 · team of 5",
        "stat": "540/540",
        "stat_label": "invoices decided",
        "lines": ["Pay, don't pay or escalate, for every invoice.", "The LLM extracts facts; versioned rules decide."],
        "stack": "Python · Pydantic · PyMuPDF · SQLite · Next.js",
    },
    {
        "id": "happytaxi",
        "sprite": "taxi",
        "name": "HAPPYTAXI",
        "context": "University project · team of 5",
        "stat": "24.6M",
        "stat_label": "NYC taxi trips",
        "lines": ["Privacy-first data platform for a taxi company,", "with two chatbots you can drive with hand gestures."],
        "stack": "Spark (Scala) · Redpanda · MongoDB · Airflow · FastAPI",
    },
    {
        "id": "flight-delays",
        "sprite": "plane",
        "name": "FLIGHT DELAYS",
        "context": "Big Data in the Cloud · team of 2",
        "stat": "GKE",
        "stat_label": "Spark in cluster mode",
        "lines": ["Flight-delay predictions served through Kafka,", "Iceberg lakehouse, Airflow + MLflow retraining."],
        "stack": "Spark ML · Kafka · Cassandra · Iceberg · Kubernetes",
    },
    {
        "id": "atalaya",
        "sprite": "tower",
        "name": "ATALAYA",
        "context": "Personal project",
        "stat": "4",
        "stat_label": "modules, one contract",
        "lines": ["Defensive security toolkit: header and TLS audits,", "secret scanning and an SSH honeypot, one CLI."],
        "stack": "Python · Typer · Pydantic · asyncssh · GitHub Actions",
    },
    {
        "id": "bad-drivers",
        "sprite": "chart",
        "name": "EUROPEAN BAD DRIVERS",
        "context": "Personal research project",
        "stat": "301,218",
        "stat_label": "injury crashes analysed",
        "lines": ["Where do people drive worse? Official crash data", "says it depends on the measure. Live observatory."],
        "stack": "Python · DuckDB · scikit-learn · React · Recharts",
    },
    {
        "id": "pokemon-spain",
        "sprite": "gamepad",
        "name": "POKEMON SPAIN",
        "context": "Side project · in progress",
        "stat": "452",
        "stat_label": "automated tests",
        "lines": ["Non-profit fangame built from the ground up in", "Godot 4: battles, breeding and a RandomLocke mode."],
        "stack": "Godot 4 · GDScript · GUT",
    },
]


def build_cards() -> None:
    W, H = 480, 250
    cw, ch = W - 6, H - 6
    pad = 24
    for p in PROJECTS:
        body = [
            f'<rect x="6" y="6" width="{cw}" height="{ch}" fill="{ACCENT_DIM}"/>',
            f'<rect x="1" y="1" width="{cw - 2}" height="{ch - 2}" fill="{BG2}" stroke="{LINE}" stroke-width="2"/>',
        ]
        markup, css = sprite(p["sprite"], pad, pad, 4)
        body.append(markup)

        su = 6
        sw = text_width(p["stat"]) * su
        body.append(pixel_text(p["stat"], cw - pad - sw, pad + 2, su, ACCENT))
        body.append(
            f'<text x="{cw - pad}" y="{pad + 5 * su + 22}" text-anchor="end" fill="{MUTED}" '
            f'font-family="{MONO}" font-size="12">{esc(p["stat_label"])}</text>'
        )

        body.append(
            f'<text x="{pad}" y="100" fill="{MUTED}" font-family="{MONO}" font-size="12">{esc(p["context"])}</text>'
        )
        tu = 4
        assert text_width(p["name"]) * tu <= cw - 2 * pad, p["name"]
        body.append(pixel_text(p["name"], pad, 112, tu, INK))
        for i, line in enumerate(p["lines"]):
            assert len(line) <= 54, line
            body.append(
                f'<text x="{pad}" y="{160 + i * 21}" fill="{INK2}" font-family="{SANS}" '
                f'font-size="15">{esc(line)}</text>'
            )
        body.append(
            f'<text x="{pad}" y="{ch - pad}" fill="{ACCENT}" font-family="{MONO}" '
            f'font-size="12">{esc(p["stack"])}</text>'
        )
        title = f'{p["name"].title()}. {p["context"]}. {" ".join(p["lines"])}'
        write(ASSETS / "cards" / f'{p["id"]}.svg', svg(W, H, "".join(body), title, css))


# --------------------------------------------------------------------------
# Inventory (tech stack)
# --------------------------------------------------------------------------

INVENTORY = [
    ("DATA", [
        ("apachespark", "Spark"), ("apacheflink", "Flink"), ("apachekafka", "Kafka"),
        ("text:RP", "Redpanda"), ("clickhouse", "ClickHouse"), ("apacheairflow", "Airflow"),
        ("databricks", "Databricks"), ("text:ICE", "Iceberg"), ("neo4j", "Neo4j"),
        ("mongodb", "MongoDB"), ("apachecassandra", "Cassandra"),
    ]),
    ("SECURITY", [
        ("wireshark", "Wireshark"), ("text:WZ", "Wazuh"), ("text:SURI", "Suricata"),
        ("owasp", "OWASP"), ("burpsuite", "Burp Suite"), ("text:NMAP", "Nmap"),
        ("vault", "Vault"), ("text:ATT&CK", "MITRE ATT&CK"),
    ]),
    ("CLOUD", [
        ("googlecloud", "Google Cloud"), ("text:AWS", "AWS"), ("text:AZ", "Azure"),
        ("terraform", "Terraform"), ("googlebigquery", "BigQuery"), ("text:S3", "S3"),
        ("cloudflare", "Cloudflare"), ("minio", "MinIO"),
    ]),
    ("AI", [
        ("pytorch", "PyTorch"), ("scikitlearn", "Scikit-learn"), ("text:XGB", "XGBoost"),
        ("huggingface", "Hugging Face"), ("mlflow", "MLflow"), ("langchain", "LangChain"),
        ("langgraph", "LangGraph"), ("ollama", "Ollama"), ("text:RAG", "RAG"),
        ("qdrant", "Qdrant"),
    ]),
    ("OPS", [
        ("docker", "Docker"), ("kubernetes", "Kubernetes"), ("github", "GitHub"),
        ("prometheus", "Prometheus"), ("grafana", "Grafana"), ("helm", "Helm"),
        ("opentelemetry", "OpenTelemetry"), ("linux", "Linux"),
    ]),
    ("CODE", [
        ("python", "Python"), ("text:SQL", "SQL"), ("typescript", "TypeScript"),
        ("fastapi", "FastAPI"), ("react", "React"), ("gnubash", "Bash"),
        ("godotengine", "Godot"), ("scala", "Scala"), ("pydantic", "Pydantic"),
    ]),
]


@functools.lru_cache(maxsize=1)
def tech_icons():
    return json.loads((SCRIPTS / "icons.json").read_text(encoding="utf-8"))["icons"]


def tech_icon(slug: str, x: float, y: float, size: float, fill: str) -> str:
    # Use explicit abbreviations when the pinned icon set has no logo. SQL and
    # RAG are concepts, so do not borrow an unrelated product's trademark.
    if slug.startswith("text:"):
        label = slug.removeprefix("text:")
        unit = min(3, (size + 22) / text_width(label))
        return pixel_text(label, x + (size - text_width(label) * unit) / 2,
                          y + (size - 5 * unit) / 2, unit, fill)
    return (f'<path transform="translate({fmt(x)} {fmt(y)}) scale({fmt(size / 24)})" '
            f'fill="{fill}" d="{tech_icons()[slug]["path"]}"/>')


def build_inventory() -> None:
    # Separate 400px panels wrap naturally in GitHub's README on narrow screens.
    # Labels remain readable instead of shrinking a single 960px inventory.
    W, pad, columns, slot, slot_h, gap, top = 400, 22, 3, 108, 72, 12, 66
    for category, items in INVENTORY:
        rows = (len(items) + columns - 1) // columns
        H = top + rows * (slot_h + gap) - gap + pad + 8
        body = [panel(W - 8, H - 8), pixel_text(category, pad, 26, 3, ACCENT)]
        body.append(
            f'<text x="{W - 8 - pad}" y="39" text-anchor="end" fill="{MUTED}" '
            f'font-family="{MONO}" font-size="12">{len(items)} items</text>'
        )
        for i, (slug, label) in enumerate(items):
            x, y = pad + (i % columns) * (slot + gap), top + (i // columns) * (slot_h + gap)
            assert x + slot <= W - 8 - 16, label
            body.append(
                f'<rect x="{x}" y="{y}" width="{slot}" height="{slot_h}" '
                f'fill="{BG2}" stroke="{LINE}" stroke-width="1"/>'
            )
            body.append(tech_icon(slug, x + (slot - 28) / 2, y + 10, 28, INK2))
            body.append(
                f'<text x="{x + slot / 2}" y="{y + 59}" text-anchor="middle" fill="{INK2}" '
                f'font-family="{SANS}" font-size="13.5">{esc(label)}</text>'
            )
        alt = f"Tech stack. {category}: {', '.join(label for _, label in items)}."
        write(ASSETS / "stack" / f"{category.lower()}.svg", svg(W, H, "".join(body), alt))


# --------------------------------------------------------------------------
# Wrapped text
# --------------------------------------------------------------------------


@functools.lru_cache(maxsize=None)
def _font(size: int, bold: bool):
    try:
        return ImageFont.truetype("segoeuib.ttf" if bold else "segoeui.ttf", size)
    except OSError:
        return None


def measure(text: str, size: int, bold: bool = False) -> float:
    """Rendered width, measured with Segoe UI plus room for wider fallback fonts."""
    f = _font(size, bold)
    width = f.getlength(text) if f else len(text) * size * 0.55
    return width * 1.07


def rich_tokens(src: str) -> list[tuple[str, str, bool]]:
    """'**bold**' and '!!accent!!' markup to (word, style, space_before) tokens."""
    tokens, style, i, word, space = [], "", 0, "", False

    def flush():
        nonlocal word, space
        if word:
            tokens.append((word, style, space))
            word, space = "", False

    while i < len(src):
        pair = src[i : i + 2]
        if pair in ("**", "!!"):
            flush()
            mark = "b" if pair == "**" else "a"
            style = "" if style == mark else mark
            i += 2
        elif src[i] == " ":
            flush()
            space = True
            i += 1
        else:
            word += src[i]
            i += 1
    flush()
    return tokens


def wrap_rich(src: str, size: int, max_width: float) -> list[list[tuple[str, str, bool]]]:
    lines, line, width = [], [], 0.0
    for word, style, space in rich_tokens(src):
        w = measure(word, size, style != "")
        gap = measure(" ", size) if line and space else 0
        if line and width + gap + w > max_width:
            lines.append(line)
            line, width = [(word, style, False)], w
        else:
            line.append((word, style, space and bool(line)))
            width += gap + w
    if line:
        lines.append(line)
    return lines


RICH_STYLE = {"": f'fill="{INK2}"', "b": f'fill="{INK}" font-weight="700"', "a": f'fill="{ACCENT}" font-weight="700"'}


def rich_line(line, x: float, y: float, size: int) -> str:
    spans = "".join(
        f'<tspan {RICH_STYLE[style]}>{" " if space else ""}{esc(word)}</tspan>' for word, style, space in line
    )
    return f'<text x="{x}" y="{y}" font-family="{SANS}" font-size="{size}" xml:space="preserve">{spans}</text>'


def plain(src: str) -> str:
    return src.replace("**", "").replace("!!", "")


def panel(w: float, h: float, y: float = 0, stroke: str = LINE, stroke_w: int = 2) -> str:
    """Panel with the hard offset shadow, occupying (w + 8) x (h + 8)."""
    return (
        f'<rect x="8" y="{y + 8}" width="{w}" height="{h}" fill="{ACCENT_DIM}"/>'
        f'<rect x="{stroke_w / 2}" y="{y + stroke_w / 2}" width="{w - stroke_w}" height="{h - stroke_w}" '
        f'fill="{BG}" stroke="{stroke}" stroke-width="{stroke_w}"/>'
    )


# --------------------------------------------------------------------------
# Section titles (light and dark versions, picked with <picture>)
# --------------------------------------------------------------------------

TITLES = [
    ("about", "ABOUT ME", ""),
    ("featured", "FEATURED PROJECTS", ""),
    ("quests", "SIDE QUESTS", "small things I made for game nights"),
    ("stack", "TECH STACK", ""),
    ("certifications", "CERTIFICATIONS", ""),
]

THEMES = {
    "dark": {"title": INK, "arrow": ACCENT, "rule": LINE, "sub": MUTED},
    "light": {"title": LIGHT_COLORS[INK], "arrow": LIGHT_COLORS[ACCENT],
              "rule": LIGHT_COLORS[LINE], "sub": LIGHT_COLORS[MUTED]},
}


def build_titles() -> None:
    W, H, u, top = 960, 60, 5, 12
    style = (
        "@keyframes drop{from{opacity:0;transform:translateY(-12px)}to{opacity:1;transform:none}}"
        ".b{animation:drop .45s cubic-bezier(.16,1,.3,1) both}"
        "@keyframes rin{from{opacity:0}to{opacity:1}}.r{animation:rin .2s both}"
        "@keyframes ab{50%{opacity:0}}.arrow{animation:ab .4s step-end .9s 4}"
    )
    for key, label, sub in TITLES:
        for theme, c in THEMES.items():
            body = [f'<g class="arrow">{pixel_text("▶", 0, top, u, c["arrow"])}</g>']
            tx = (text_width("▶") + 3) * u
            blocks = []
            for bx, by, ci, row, col in pixel_blocks(label, tx, top, u):
                delay = 0.05 + ci * 0.035 + pseudo_random(ci, row, col, len(label)) * 0.2
                blocks.append(
                    f'<rect class="b" style="animation-delay:{delay:.2f}s" x="{fmt(bx)}" y="{fmt(by)}" '
                    f'width="{u}" height="{u}"/>'
                )
            body.append(f'<g fill="{c["title"]}">{"".join(blocks)}</g>')
            if sub:
                sx = tx + text_width(label) * u + 22
                body.append(
                    f'<text x="{sx}" y="{top + 5 * u - 3}" fill="{c["sub"]}" font-family="{MONO}" '
                    f'font-size="14">{esc(sub)}</text>'
                )
            rule = "".join(
                f'<rect class="r" style="animation-delay:{0.15 + i * 0.006:.3f}s" x="{i * 12}" y="50" '
                f'width="8" height="4"/>'
                for i in range(80)
            )
            body.append(f'<g fill="{c["rule"]}">{rule}</g>')
            alt = label.capitalize() + (f": {sub}" if sub else "")
            write(ASSETS / "titles" / f"{key}-{theme}.svg", svg(W, H, "".join(body), alt, style))


# --------------------------------------------------------------------------
# About me: a dialogue box that types itself out once
# --------------------------------------------------------------------------

SPEAKER = "JAVIER"
ABOUT = [
    "I'm Javier, a final-year **Data Engineering & Systems** student at **ETSIT-UPM** in Madrid. "
    "Most of what I build sits where data meets infrastructure: pipelines that stream, store and "
    "serve data, and the platforms around them.",
    "I also care about security. I co-founded **FORTIA Security**, a cybersecurity consultancy for "
    "small businesses (web security audits, phishing simulations and staff training), and I write my "
    "own defensive tools.",
    "And sometimes I build just for fun: party games for my friends, a poker chip counter for nights "
    "without chips, and a whole Pokémon fangame.",
    "!!Right now:!! my bachelor's thesis, a cyber situational awareness platform that turns raw "
    "security telemetry into correlated, explainable incidents. Redpanda, Sigma rules, multi-stage "
    "detection, Neo4j attack graphs and MITRE ATT&CK.",
]


def build_about() -> None:
    W = 960
    size, lh, pgap, padx = 17, 28, 14, 44
    box_top = 22
    bw = W - 8
    paragraphs = [wrap_rich(p, size, bw - 2 * padx) for p in ABOUT]
    n_lines = sum(len(p) for p in paragraphs)
    text_top = box_top + 58
    bh = text_top - box_top + (n_lines - 1) * lh + (len(paragraphs) - 1) * pgap + 46
    H = box_top + bh + 8

    body = [panel(bw, bh, box_top, INK, 4)]
    tab_w = text_width(SPEAKER) * 3 + 32
    body.append(f'<rect x="30" y="6" width="{tab_w}" height="34" fill="{BG}" stroke="{INK}" stroke-width="4"/>')
    body.append(pixel_text(SPEAKER, 46, 16, 3, ACCENT))
    body.append(
        f'<defs><clipPath id="box"><rect x="4" y="{box_top + 4}" width="{bw - 8}" height="{bh - 8}"/></clipPath></defs>'
    )

    # Each line is uncovered left to right, in steps, one after another.
    style = []
    texts, covers = [], []
    t, y, i = 0.5, text_top, 0
    right = bw - 4
    for para in paragraphs:
        for line in para:
            texts.append(rich_line(line, padx, y, size))
            chars = sum(len(w) + (1 if s else 0) for w, _, s in line)
            dur = max(0.25, chars * 0.006)
            x0 = padx - 2
            dist = right - x0
            style.append(
                f"@keyframes w{i}{{from{{transform:translateX(0)}}to{{transform:translateX({fmt(dist)}px)}}}}"
                f".w{i}{{animation:w{i} {dur:.2f}s steps({max(8, chars // 2)}) {t:.2f}s both}}"
            )
            covers.append(
                f'<rect class="w{i}" style="transform:translateX({fmt(dist)}px)" x="{x0}" y="{y - size - 4}" '
                f'width="{fmt(dist)}" height="{lh}" fill="{BG}"/>'
            )
            t += dur + 0.04
            y += lh
            i += 1
        t += 0.2
        y += pgap
    body.append(f'<g clip-path="url(#box)">{"".join(texts)}{"".join(covers)}</g>')

    # Blinking "next" arrow once everything is written.
    style.append(
        "@keyframes show{from{opacity:0}to{opacity:1}}"
        f".next{{animation:show .01s {t:.2f}s both}}"
        "@keyframes blink{50%{opacity:0}}.next g{animation:blink .9s step-end infinite}"
    )
    arrow = sprite_rects(["ggggg", ".ggg.", "..g.."], 0, 0, 3)
    body.append(
        f'<g class="next" transform="translate({bw - 46} {box_top + bh - 30})"><g>{arrow}</g></g>'
    )

    alt = "About me. " + " ".join(plain(p) for p in ABOUT)
    write(ASSETS / "about.svg", svg(W, int(H), "".join(body), alt, "".join(style)))


# --------------------------------------------------------------------------
# Live demo buttons
# --------------------------------------------------------------------------

DEMOS = [("albertitos", "ALBERTITOS"), ("happytaxi", "HAPPYTAXI"), ("observatory", "OBSERVATORY")]


def build_demo_buttons() -> None:
    W, H = 262, 64
    for i, (key, label) in enumerate(DEMOS):
        body = [
            f'<rect x="5" y="5" width="{W - 5}" height="{H - 5}" fill="{ACCENT_DIM}"/>',
            f'<rect x="1" y="1" width="{W - 7}" height="{H - 7}" fill="{BG2}" stroke="{ACCENT}" stroke-width="2"/>',
        ]
        markup, css = sprite("play", 10, (H - 5 - 36) / 2, 3, delay=i * 0.4)
        body.append(markup)
        tx = 56
        assert tx + text_width(label) * 3 < W - 17, label
        body.append(
            f'<text x="{tx}" y="24" fill="{MUTED}" font-family="{MONO}" font-size="11">LIVE DEMO</text>'
        )
        body.append(pixel_text(label, tx, 31, 3, INK))
        write(ASSETS / "buttons" / f"demo-{key}.svg", svg(W, H, "".join(body), f"Live demo: {label.title()}", css))


# --------------------------------------------------------------------------
# Also built for class
# --------------------------------------------------------------------------

COURSEWORK = [
    ("lidar", "KITTI", ["Object detection (YOLO) and", "LiDAR-to-camera projection"]),
    ("brain", "BRATS", ["Self-supervised brain tumour", "detection, contrastive learning"]),
    ("hand", "HAND GESTURES", ["Gesture recognition with", "MediaPipe and a CNN"]),
]


def build_coursework() -> None:
    W, H = 960, 166
    body = [panel(W - 8, H - 8), pixel_text("ALSO BUILT FOR CLASS", 28, 26, 3, ACCENT)]
    for k, (spr, name, lines) in enumerate(COURSEWORK):
        x = 28 + k * 302
        markup, css = sprite(spr, x, 66, 4, delay=k * 0.4)
        body.append(markup)
        assert text_width(name) * 3 < 230, name
        body.append(pixel_text(name, x + 64, 68, 3, INK))
        for j, line in enumerate(lines):
            assert measure(line, 14) < 236, line
            body.append(
                f'<text x="{x + 64}" y="{106 + j * 20}" fill="{INK2}" font-family="{SANS}" font-size="14">{esc(line)}</text>'
            )
    alt = "Also built for class: " + "; ".join(f"{n.title()}: {' '.join(l)}" for _, n, l in COURSEWORK) + "."
    write(ASSETS / "coursework.svg", svg(W, H, "".join(body), alt, SPRITE_CSS))


# --------------------------------------------------------------------------
# Side quests
# --------------------------------------------------------------------------

QUESTS = [
    ("poker", "chip", "POKER CHIPS", ["A Texas Hold'em chip counter for", "when nobody brought chips."]),
    ("wavelength", "dial", "WAVELENGTH", ["The party guessing game,", "on one phone."]),
    ("tabu", "cards", "TABU", ["Cards for game nights."]),
    ("bet366", "dice", "BET366", ["A betting house for friends.", "Points only, never real money."]),
]


def build_quests() -> None:
    W, H = 480, 150
    cw, ch = W - 6, H - 6
    for i, (key, spr, name, lines) in enumerate(QUESTS):
        body = [
            f'<rect x="6" y="6" width="{cw}" height="{ch}" fill="{ACCENT_DIM}"/>',
            f'<rect x="1" y="1" width="{cw - 2}" height="{ch - 2}" fill="{BG2}" stroke="{LINE}" stroke-width="2"/>',
        ]
        markup, css = sprite(spr, 24, 26, 4, delay=i * 0.3)
        body.append(markup)
        body.append(f'<text x="88" y="38" fill="{MUTED}" font-family="{MONO}" font-size="12">Side quest</text>')
        body.append(pixel_text(name, 88, 48, 4, INK))
        play = "PLAY ▶"
        body.append(pixel_text(play, cw - 24 - text_width(play) * 3, 28, 3, ACCENT))
        for j, line in enumerate(lines):
            assert measure(line, 15) < cw - 88 - 20, line
            body.append(
                f'<text x="88" y="{98 + j * 21}" fill="{INK2}" font-family="{SANS}" font-size="15">{esc(line)}</text>'
            )
        write(ASSETS / "quests" / f"{key}.svg", svg(W, H, "".join(body), f"{name.title()}. {' '.join(lines)}", css))


# --------------------------------------------------------------------------
# Certifications
# --------------------------------------------------------------------------

CERTS = [
    {"id": "google", "issuer": "GOOGLE", "icon": "google",
     "lines": [("Cybersecurity", 21), ("Professional Certificate", 16)],
     "alt": "Google Cybersecurity Professional Certificate"},
    {"id": "tryhackme", "issuer": "TRYHACKME", "icon": "tryhackme",
     "lines": [("Jr Penetration", 21), ("Tester", 21)],
     "alt": "TryHackMe Jr Penetration Tester"},
]


def build_certifications() -> None:
    W, H = 400, 204
    for cert in CERTS:
        body = [panel(W - 8, H - 8)]
        # A larger stepped medallion, inset face and two cut ribbons extend the
        # existing pixel-art system. The centre uses the real issuer's logo.
        body.append(
            f'<path d="M49 115H76L70 175L58 163L44 173Z" fill="{ACCENT_DIM}" stroke="{ACCENT}" stroke-width="2"/>'
            f'<path d="M80 115H107L112 173L98 163L86 175Z" fill="{ACCENT_DIM}" stroke="{ACCENT}" stroke-width="2"/>'
            f'<path d="M58 127L54 157M96 127L100 157" fill="none" stroke="{ACCENT}" stroke-width="4"/>'
            f'<path d="M42 50H54V38H102V50H114V62H126V110H114V122H102V134H54V122H42V110H30V62H42Z" '
            f'fill="{ACCENT_DIM}" stroke="{ACCENT}" stroke-width="3"/>'
            f'<path d="M50 62H62V50H94V62H106V74H114V98H106V110H94V122H62V110H50V98H42V74H50Z" '
            f'fill="{BG2}" stroke="{ACCENT}" stroke-width="2"/>'
            f'<path d="M54 66V60H66M94 112H102V104" fill="none" stroke="{INK}" stroke-width="3"/>'
        )
        body.append(tech_icon(cert["icon"], 58, 66, 40, INK))
        body.append(pixel_text(cert["issuer"], 152, 44, 3, ACCENT))
        for j, (line, size) in enumerate(cert["lines"]):
            assert measure(line, size, True) < W - 152 - 24, line
            body.append(
                f'<text x="152" y="{99 + j * 29}" fill="{INK}" font-family="{SANS}" '
                f'font-size="{size}" font-weight="700">{esc(line)}</text>'
            )
        alt = f'Certifications: {cert["alt"]}.'
        write(ASSETS / "certifications" / f'{cert["id"]}.svg', svg(W, H, "".join(body), alt))


# --------------------------------------------------------------------------
# Footer
# --------------------------------------------------------------------------

FOOTER = "BUILT BLOCK BY BLOCK IN MADRID"


def build_footer() -> None:
    W, H, u = 960, 40, 2
    tw = (text_width(FOOTER) + 3) * u
    x = (W - tw) / 2
    style = "@keyframes blink{50%{opacity:0}}.cur{animation:blink 1s step-end infinite}"
    for theme, c in THEMES.items():
        body = pixel_text(FOOTER, x, 15, u, c["sub"]) + (
            f'<rect class="cur" x="{x + (text_width(FOOTER) + 2) * u}" y="15" width="{2 * u}" '
            f'height="{5 * u}" fill="{c["arrow"]}"/>'
        )
        write(ASSETS / f"footer-{theme}.svg", svg(W, H, body, "Built block by block in Madrid.", style))


if __name__ == "__main__":
    build_header()
    build_buttons()
    build_demo_buttons()
    build_cards()
    build_inventory()
    build_titles()
    build_about()
    build_coursework()
    build_quests()
    build_certifications()
    build_footer()
