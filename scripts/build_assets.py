"""Builds the SVG assets of the profile README.

    python scripts/build_assets.py

Everything is drawn here: a 5x5 pixel font, small sprites and the layouts.
No web fonts, no scripts and no third-party image services, so GitHub can
serve the files as they are. Edit the content lists (ABOUT, PROJECTS,
QUESTS, INVENTORY...) and run it again.
"""

from __future__ import annotations

import base64
import functools
import io
import json
from pathlib import Path

from PIL import Image, ImageFont

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
    "DATA PIPELINES THAT STREAM",
    "SECURITY TOOLS FOR WHAT I SHIP",
    "PARTY GAMES FOR MY FRIENDS",
    "A POKEMON FANGAME, FROM SCRATCH",
]


def avatar_data_uri(size: int) -> str:
    """Square crop of the portrait, embedded so GitHub needs no extra request."""
    src = next(
        (p for p in (SCRIPTS / "avatar.jpg", SCRIPTS / "avatar.png") if p.exists()), None
    )
    if src is None:
        raise SystemExit("put the portrait at scripts/avatar.jpg or scripts/avatar.png")
    im = Image.open(src).convert("RGB")
    crop = json.loads((SCRIPTS / "avatar_crop.json").read_text()) if (SCRIPTS / "avatar_crop.json").exists() else None
    if crop:
        im = im.crop((crop["left"], crop["top"], crop["left"] + crop["size"], crop["top"] + crop["size"]))
    else:
        side = min(im.size)
        im = im.crop(((im.width - side) // 2, (im.height - side) // 2, (im.width + side) // 2, (im.height + side) // 2))
    resample = Image.NEAREST if im.width <= 128 else Image.LANCZOS
    im = im.resize((size, size), resample)
    buf = io.BytesIO()
    if resample is Image.NEAREST:
        im.save(buf, "PNG", optimize=True)
        mime = "image/png"
    else:
        im.save(buf, "JPEG", quality=86, optimize=True, progressive=True)
        mime = "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(buf.getvalue()).decode()}"


def build_header() -> None:
    W, H = 960, 330
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

    # Portrait in a pixel frame, with HP and XP bars.
    ax, ay, asz = 40, 40, 200
    body.append(f'<rect x="{ax + 8}" y="{ay + 8}" width="{asz}" height="{asz}" fill="{ACCENT_DIM}"/>')
    body.append(f'<rect x="{ax - 4}" y="{ay - 4}" width="{asz + 8}" height="{asz + 8}" fill="{INK}"/>')
    body.append(
        f'<image x="{ax}" y="{ay}" width="{asz}" height="{asz}" preserveAspectRatio="xMidYMid slice" '
        f'href="{avatar_data_uri(400)}"/>'
    )
    bars = [("HP", 9), ("XP", 6)]
    style.append("@keyframes pip{from{opacity:.12}to{opacity:1}}")
    style.append(".pip{animation:pip .25s ease-out both}")
    for b, (label, lit) in enumerate(bars):
        by = ay + asz + 22 + b * 22
        body.append(pixel_text(label, ax - 4, by, 2, MUTED))
        for i in range(10):
            px = ax + 22 + i * 18
            if i < lit:
                delay = 0.5 + b * 0.25 + i * 0.07
                body.append(
                    f'<rect class="pip" style="animation-delay:{delay:.2f}s" x="{px}" y="{by}" '
                    f'width="14" height="10" fill="{ACCENT}"/>'
                )
            else:
                body.append(f'<rect x="{px}" y="{by}" width="14" height="10" fill="{LINE}"/>')

    tx = 290
    body.append(pixel_text(ROLE, tx, 44, 3, ACCENT))

    # Name, dropped in block by block.
    style.append("@keyframes drop{from{opacity:0;transform:translateY(-18px)}to{opacity:1;transform:none}}")
    style.append(".b{animation:drop .5s cubic-bezier(.16,1,.3,1) both}")
    unit = 12
    blocks = []
    offset = 0
    for li, word in enumerate(NAME):
        y = 80 + li * (5 * unit + 14)
        for bx, by, ci, row, col in pixel_blocks(word, tx, y, unit):
            delay = 0.1 + (offset + ci) * 0.06 + pseudo_random(li, ci, row, col) * 0.35
            blocks.append(
                f'<rect class="b" style="animation-delay:{delay:.2f}s" x="{fmt(bx)}" y="{fmt(by)}" '
                f'width="{unit}" height="{unit}"/>'
            )
        offset += len(word)
    body.append(f'<g fill="{INK}">{"".join(blocks)}</g>')

    body.append(
        f'<text x="{tx}" y="250" fill="{INK2}" font-family="{SANS}" font-size="19">{esc(SUBTITLE)}</text>'
    )

    # Typed lines: a cover the colour of the panel slides off each line,
    # one character at a time, then slides back.
    tu = 4
    ty = 270
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
        "id": "panchito",
        "sprite": "gamepad",
        "name": "POKEMON PANCHITO",
        "context": "Side project · in progress",
        "stat": "452",
        "stat_label": "automated tests",
        "lines": ["Non-profit fangame built from scratch in Godot 4:", "battles, breeding and a RandomLocke mode."],
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
        ("apachespark", "Spark"), ("scala", "Scala"), ("apachekafka", "Kafka"),
        ("apacheairflow", "Airflow"), ("mongodb", "MongoDB"), ("apachecassandra", "Cassandra"),
        ("mlflow", "MLflow"), ("duckdb", "DuckDB"),
    ]),
    ("SECURITY", [
        ("kalilinux", "Kali"), ("wireshark", "Wireshark"), ("metasploit", "Metasploit"),
        ("burpsuite", "Burp Suite"), ("tryhackme", "TryHackMe"), ("owasp", "OWASP"),
    ]),
    ("CLOUD & OPS", [
        ("docker", "Docker"), ("kubernetes", "Kubernetes"), ("googlecloud", "GCP"),
        ("prometheus", "Prometheus"), ("grafana", "Grafana"), ("githubactions", "Actions"),
        ("linux", "Linux"), ("vercel", "Vercel"),
    ]),
    ("CODE", [
        ("python", "Python"), ("typescript", "TypeScript"), ("fastapi", "FastAPI"),
        ("react", "React"), ("nextdotjs", "Next.js"), ("godotengine", "Godot"),
        ("gnubash", "Bash"), ("sqlite", "SQL"),
    ]),
]


def build_inventory() -> None:
    icons = json.loads((SCRIPTS / "icons.json").read_text(encoding="utf-8"))["icons"]
    W = 960
    pad = 28
    slot, gap = 80, 10
    label_w = 150
    top = 64
    pitch = slot + 12
    H = top + len(INVENTORY) * pitch - 12 + pad + 8
    pw, ph = W - 8, H - 8

    body = [
        f'<rect x="8" y="8" width="{pw}" height="{ph}" fill="{ACCENT_DIM}"/>',
        f'<rect width="{pw}" height="{ph}" fill="{BG}" stroke="{LINE}" stroke-width="2"/>',
        pixel_text("INVENTORY", pad, pad, 3, ACCENT),
    ]
    count = sum(len(items) for _, items in INVENTORY)
    body.append(
        f'<text x="{pw - pad}" y="{pad + 13}" text-anchor="end" fill="{MUTED}" font-family="{MONO}" '
        f'font-size="13">{count} items</text>'
    )

    positions = []
    for r, (category, items) in enumerate(INVENTORY):
        y = top + r * pitch
        body.append(pixel_text(category, pad, y + slot / 2 - 5, 2, INK2))
        for c, (slug, label) in enumerate(items):
            x = pad + label_w + c * (slot + gap)
            positions.append((x, y))
            i = len(positions) - 1
            body.append(f'<rect x="{x}" y="{y}" width="{slot}" height="{slot}" fill="{BG2}" stroke="{LINE}" stroke-width="2"/>')
            s = 30 / 24
            body.append(
                f'<path class="i{i}" transform="translate({x + (slot - 30) / 2} {y + 13}) scale({s})" '
                f'fill="{INK2}" d="{icons[slug]["path"]}"/>'
            )
            body.append(
                f'<text x="{x + slot / 2}" y="{y + slot - 13}" text-anchor="middle" fill="{MUTED}" '
                f'font-family="{MONO}" font-size="11">{esc(label)}</text>'
            )

    # A selection cursor walks the slots and lights each item up.
    step = 0.9
    total = step * len(positions)
    style = []
    cursor_frames = []
    for i, (x, y) in enumerate(positions):
        p0 = 100 * i / len(positions)
        p1 = 100 * (i + 1) / len(positions)
        cursor_frames.append(f"{p0:.3f}%{{transform:translate({x}px,{y}px)}}")
        on = [f"0%{{fill:{INK2}}}", f"{p0:.3f}%{{fill:{ACCENT}}}", f"{p1:.3f}%{{fill:{INK2}}}", f"100%{{fill:{INK2}}}"]
        if i == 0:
            on = [f"0%{{fill:{ACCENT}}}", f"{p1:.3f}%{{fill:{INK2}}}", f"100%{{fill:{INK2}}}"]
        style.append(f"@keyframes k{i}{{{''.join(on)}}}.i{i}{{animation:k{i} {total:.1f}s step-end infinite}}")
    style.append(f"@keyframes walk{{{''.join(cursor_frames)}}}")
    style.append(f".cursor{{animation:walk {total:.1f}s step-end infinite}}")

    # Four pixel corner brackets around a slot.
    o, arm, t = -5, 14, 4
    far = slot + 5
    corners = []
    for cx, cy, dx, dy in ((o, o, 1, 1), (far, o, -1, 1), (o, far, 1, -1), (far, far, -1, -1)):
        hx = cx if dx > 0 else cx - arm
        vy = cy if dy > 0 else cy - arm
        corners.append(f'<rect x="{hx}" y="{cy if dy > 0 else cy - t}" width="{arm}" height="{t}"/>')
        corners.append(f'<rect x="{cx if dx > 0 else cx - t}" y="{vy}" width="{t}" height="{arm}"/>')
    x0, y0 = positions[0]
    body.append(
        f'<g class="cursor" fill="{ACCENT}" style="transform:translate({x0}px,{y0}px)">{"".join(corners)}</g>'
    )

    alt = "Tech stack. " + " ".join(
        f"{cat.title()}: {', '.join(label for _, label in items)}." for cat, items in INVENTORY
    )
    write(ASSETS / "inventory.svg", svg(W, H, "".join(body), alt, "".join(style)))


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
    """Dark panel with the hard offset shadow, occupying (w + 8) x (h + 8)."""
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
    ("activity", "ACTIVITY", ""),
]

THEMES = {
    "dark": {"title": INK, "arrow": ACCENT, "rule": "#30363d", "sub": MUTED},
    "light": {"title": "#1f2328", "arrow": ACCENT_DIM, "rule": "#d0d7de", "sub": "#59636e"},
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

CERTS = [("Google Cybersecurity", "Professional Certificate"), ("TryHackMe", "Jr Penetration Tester")]


def build_certifications() -> None:
    W, H = 960, 148
    body = [panel(W - 8, H - 8)]
    style = [
        SPRITE_CSS,
        "@keyframes pop{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}"
        ".pop{animation:pop .5s cubic-bezier(.16,1,.3,1) both}",
    ]
    for k, lines in enumerate(CERTS):
        x = 32 + k * 460
        markup, _ = sprite("medal", x, 38, 5, delay=k * 0.6)
        text = "".join(
            f'<text x="{x + 88}" y="{84 + j * 25}" fill="{INK}" font-family="{SANS}" font-size="19" '
            f'font-weight="700">{esc(line)}</text>'
            for j, line in enumerate(lines)
        )
        body.append(
            f'<g class="pop" style="animation-delay:{0.2 + k * 0.25:.2f}s">{markup}'
            f'<text x="{x + 88}" y="56" fill="{MUTED}" font-family="{MONO}" font-size="12">Certificate</text>'
            f"{text}</g>"
        )
    alt = "Certifications: " + "; ".join(" ".join(c) for c in CERTS) + "."
    write(ASSETS / "certifications.svg", svg(W, H, "".join(body), alt, "".join(style)))


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
