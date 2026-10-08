"""Convert the prepped image into a monochrome ASCII-art SVG that "types" itself in,
then loops: blink, morph into the coding scene (typing + coffee steam), and back.

Each row is revealed by a left-to-right clip wipe with a block cursor riding the edge,
staggered top to bottom. Plays once and freezes (SMIL, so GitHub's <img> renders it).

Usage: python scripts/make_ascii_svg.py            # writes ascii-portrait.svg
       STATIC=1 python scripts/make_ascii_svg.py   # frozen frame, no animation
"""
import math
import os
import random
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source-prepped.png"
OUT = ROOT / "ascii-portrait.svg"
SCENE_SRC = ROOT / "source-coding-prepped.png"  # second art the portrait morphs into
SCENE_DIM_BOX = (0.68, 0.5)  # (x, y) grid fractions: right/bottom area where the laptop sits
# Boxes in scene-image pixels (x0, y0, x1, y1).
SCENE_HAND = (560, 860, 700, 950)  # fingers on the keyboard
SCENE_MUG = (300, 900, 468, 1050)  # coffee mug (top edge = rim)

RAMP = " .`:-=+*cs#%@"  # bright (sparse) -> dark (dense); leading space clears the background
COLS = 120
SHADES = [".55", ".6", ".78", "1"]  # glyph opacity per density band, sparse -> dense
GAMMA = 1.0  # <1 lightens mid-tones (sparser skin, outlines pop), >1 darkens them
LINE_WEIGHT = 0.5  # 0..1: how much each cell's darkest pixels count (keeps thin outlines)
POSITIVE = True  # bright -> dense (reads like the source); False = classic negative look
CROP_BOTTOM = 0.8  # keep this fraction of the subject's height (trim the neck)
FONT_SIZE = 8.4
CHAR_W = 5.0  # forced via textLength, so the grid stays aligned in any monospace font
LINE_H = 10.0
PAD = 24
BG = "#0d1117"
BORDER = "#30363d"
FG = "#c9d1d9"
CURSOR = "#39d353"

ROW_DELAY = 0.04  # seconds between row starts
ROW_DUR = 0.35  # seconds for one row's wipe
START = 0.2

# Boxes in source-image pixels (x0, y0, x1, y1), mapped onto the character grid.
EYES = [(355, 430, 425, 480), (505, 425, 575, 478)]
BLINK_EVERY = 1.2  # seconds between blinks

# Morph loop: face -> scene -> face, forever (seconds).
FACE_HOLD = 4.0
SCENE_HOLD = 3.0
MORPH_DUR = 1.0
MORPH_FRAMES = 5
SCRAMBLE = "#%&$?@*+=/<>"

STATIC = os.environ.get("STATIC") == "1"


def dark_pool(arr: np.ndarray, cols: int, rows: int) -> np.ndarray:
    """Per-cell 10th-percentile brightness: close to the darkest pixel, minus stray noise."""
    ys = np.linspace(0, arr.shape[0], rows + 1).astype(int)
    xs = np.linspace(0, arr.shape[1], cols + 1).astype(int)
    out = np.empty((rows, cols), np.float32)
    for r in range(rows):
        band = arr[ys[r]:ys[r + 1]]
        for c in range(cols):
            out[r, c] = np.percentile(band[:, xs[c]:xs[c + 1]], 10)
    return out


def load_grid(src: Path = SRC, crop_bottom: float = CROP_BOTTOM, cols: int = COLS
              ) -> tuple[list[str], callable]:
    img = Image.open(src).convert("L")
    arr = np.asarray(img, dtype=np.float32)
    subject = arr < 250  # the prep step composited the background to pure white

    # Crop to the subject (plus a small margin) so the grid isn't spent on empty space.
    ys, xs = np.nonzero(subject)
    m = 6
    y0, y1 = max(ys.min() - m, 0), min(ys.max() + m, arr.shape[0])
    x0, x1 = max(xs.min() - m, 0), min(xs.max() + m, arr.shape[1])
    y1 = y0 + round((y1 - y0) * crop_bottom)
    arr, subject = arr[y0:y1, x0:x1], subject[y0:y1, x0:x1]

    # Stretch the subject's own tonal range to the full ramp; keep the background white.
    lo, hi = np.percentile(arr[subject], [2, 98])
    stretched = ((arr - lo) / max(hi - lo, 1.0) * 255.0).clip(0, 245) ** GAMMA / 245.0 ** (GAMMA - 1)
    arr = np.where(subject, stretched, 255.0)

    # Character cells are taller than wide, so sample fewer rows than columns.
    rows = round(cols * (arr.shape[0] / arr.shape[1]) * (CHAR_W / LINE_H))
    img = Image.fromarray(arr.astype(np.uint8), "L")
    small = np.asarray(img.resize((cols, rows), Image.Resampling.BOX), dtype=np.float32)
    if LINE_WEIGHT:
        # Thin dark outlines vanish when a whole cell is averaged; mix in each cell's darkest
        # pixel so line art (glasses, eyes, jaw) survives the downsample.
        small = small * (1 - LINE_WEIGHT) + dark_pool(arr, cols, rows) * LINE_WEIGHT
    if POSITIVE:
        # Light text on a dark terminal: bright areas print dense, so it reads like the
        # original. The subject's darkest areas still get a faint glyph (not a space)
        # so dark hair keeps its silhouette.
        mask = np.asarray(Image.fromarray(subject.astype(np.uint8) * 255).resize((cols, rows), Image.Resampling.BOX))
        idx = 2 + (small / 256.0 * (len(RAMP) - 2)).astype(int).clip(0, len(RAMP) - 3)
        idx = np.where(mask > 127, idx, 0)
    else:
        idx = ((255.0 - small) / 256.0 * len(RAMP)).astype(int).clip(0, len(RAMP) - 1)
    lines = ["".join(RAMP[i] for i in row) for row in idx]
    # Trim blank rows top and bottom so the portrait sits snug in its frame.
    top = 0
    while lines and not lines[0].strip():
        lines.pop(0)
        top += 1
    while lines and not lines[-1].strip():
        lines.pop()

    def to_cell(x: float, y: float) -> tuple[int, int]:
        """Source-image pixel -> (col, row) in the trimmed grid."""
        col = (x - x0) / (x1 - x0) * cols
        row = (y - y0) / (y1 - y0) * rows - top
        return round(col), round(row)

    return lines, to_cell


def esc(s: str) -> str:
    # Non-breaking spaces can't be collapsed by the renderer, so columns stay put.
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace(" ", "&#160;")


def shade(line: str) -> str:
    """Denser glyphs also print brighter, so tone reads through even at tiny sizes.

    Runs of characters in the same brightness band share one <tspan> to keep the file small.
    """
    bands = len(SHADES)
    parts, run, run_band = [], "", None
    for ch in line:
        if ch == " ":
            band = None
        elif ch in RAMP:
            band = min(RAMP.index(ch) * bands // len(RAMP), bands - 1)
        else:
            band = bands - 1  # scramble glyphs (/ ? & etc.) print at full brightness
        if run and band != run_band and not (ch == " " and run_band is None):
            parts.append((run_band, run))
            run = ""
        if not run:
            run_band = band
        run += ch
    if run:
        parts.append((run_band, run))
    return "".join(
        esc(text) if band is None else f'<tspan fill-opacity="{SHADES[band]}">{esc(text)}</tspan>'
        for band, text in parts
    )


def face_fx(lines: list[str], to_cell, art_y: float, done: float) -> list[str]:
    """Looping blink: the eye glyphs swap to closed lids for a moment."""
    if STATIC:
        return []
    out = []

    # Blink: cover each eye with skin-toned glyphs and a lid line for ~150 ms.
    font = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"
    on = 0.15 / BLINK_EVERY
    for bx0, by0, bx1, by1 in EYES:
        c0, r0 = to_cell(bx0, by0)
        c1, r1 = to_cell(bx1, by1)
        r0, r1 = max(r0, 0), min(r1, len(lines))
        ring = [lines[r][c] for r in (r0 - 1, r1) if 0 <= r < len(lines) for c in range(c0, c1)]
        skin = max(set(ring) - {" "}, key=ring.count, default=":")
        n = c1 - c0
        rows = []
        for r in range(r0, r1):
            text = ("-" + "=" * (n - 2) + "-") if r == (r0 + r1) // 2 else skin * n
            y = art_y + r * LINE_H + LINE_H * 0.8
            rows.append(
                f'<text x="{PAD + c0 * CHAR_W:g}" y="{y:g}" textLength="{n * CHAR_W:g}" '
                f'lengthAdjust="spacingAndGlyphs">{shade(text)}</text>'
            )
        out.append(
            f'<g opacity="0" font-family="{font}" font-size="{FONT_SIZE}" fill="{FG}">'
            f'<rect x="{PAD + c0 * CHAR_W:g}" y="{art_y + r0 * LINE_H:g}" width="{n * CHAR_W:g}" '
            f'height="{(r1 - r0) * LINE_H:g}" fill="{BG}"/>{"".join(rows)}'
            f'<animate attributeName="opacity" values="0;1;0" keyTimes="0;{1 - on:.3f};1" calcMode="discrete" '
            f'dur="{BLINK_EVERY}s" begin="{done + 0.8:.2f}s" repeatCount="indefinite"/></g>'
        )
    return out


def scene_grid(n_rows: int) -> tuple[list[str], callable]:
    """The second art on the same COLS x n_rows grid as the face, centred, plus a
    scene-pixel -> (col, row) mapper for placing effects."""
    cols = COLS
    while True:
        lines, to_cell = load_grid(SCENE_SRC, 1.0, cols)
        if len(lines) <= n_rows:
            break
        cols -= 2
    side = (COLS - cols) // 2
    lines = [" " * side + line + " " * (COLS - cols - side) for line in lines]
    top = (n_rows - len(lines)) // 2
    blank = " " * COLS
    grid = [blank] * top + lines + [blank] * (n_rows - len(lines) - top)
    # The laptop's lit edge is the brightest thing in the picture and prints as a
    # glaring white "@" streak; flatten it to the lid's own glyph.
    x0, y0 = SCENE_DIM_BOX[0] * COLS, SCENE_DIM_BOX[1] * n_rows
    grid = [
        "".join("*" if ch in "@%" and c >= x0 and r >= y0 else ch for c, ch in enumerate(line))
        for r, line in enumerate(grid)
    ]

    def scene_cell(x: float, y: float) -> tuple[int, int]:
        c, r = to_cell(x, y)
        return c + side, r + top

    return grid, scene_cell


def morph_frames(a: list[str], b: list[str]) -> list[list[str]]:
    """In-between grids from a to b: a diagonal front sweeps across; cells just behind
    it show scrambled glyphs, cells past it show b."""
    rng = random.Random(5)
    rows, cols = len(a), len(a[0])
    span = cols + 2 * rows
    order = [[(c + 2 * r) / span * 0.8 + rng.uniform(0, 0.2) for c in range(cols)] for r in range(rows)]
    band = 0.18
    frames = []
    for j in range(1, MORPH_FRAMES + 1):
        p = j / (MORPH_FRAMES + 1) * (1 + band)
        grid = []
        for r in range(rows):
            row = []
            for c in range(cols):
                o = order[r][c]
                if o < p - band:
                    row.append(b[r][c])
                elif o < p and (a[r][c] != " " or b[r][c] != " "):
                    row.append(rng.choice(SCRAMBLE))
                else:
                    row.append(a[r][c])
            grid.append("".join(row))
        frames.append(grid)
    return frames


def group(windows: list[tuple[float, float]], cycle: float, begin: float, initially: bool,
          attrs: str = "") -> str:
    """Opening <g> tag (plus its animation) that is visible only inside the given
    (start, end) windows of each cycle. Close it with "</g>"."""
    events = [(0.0, 0.0)]
    for t0, t1 in windows:
        events += [(t0, 1.0), (t1, 0.0)]
    steps: dict[float, float] = {}
    for t, v in events:
        steps[round(t / cycle, 4)] = v
    keys = sorted(k for k in steps if k < 1)
    vals = ";".join(f"{steps[k]:g}" for k in keys)
    return (
        f'<g{attrs} opacity="{1 if initially else 0}"><animate attributeName="opacity" values="{vals}" '
        f'keyTimes="{";".join(f"{k:g}" for k in keys)}" calcMode="discrete" dur="{cycle:.2f}s" '
        f'begin="{begin:.2f}s" repeatCount="indefinite"/>'
    )


def grid_text(grid: list[str], art_y: float) -> list[str]:
    text_w = COLS * CHAR_W
    return [
        f'<text x="{PAD}" y="{art_y + i * LINE_H + LINE_H * 0.8:g}" textLength="{text_w:g}" '
        f'lengthAdjust="spacingAndGlyphs">{shade(line)}</text>'
        for i, line in enumerate(grid) if line.strip()
    ]


def cells_text(col: int, row: int, text: str, art_y: float) -> str:
    """A run of glyphs placed exactly on the grid, with a background patch under it."""
    x, y, n = PAD + col * CHAR_W, art_y + row * LINE_H, len(text)
    return (
        f'<rect x="{x:g}" y="{y:g}" width="{n * CHAR_W:g}" height="{LINE_H:g}" fill="{BG}"/>'
        f'<text x="{x:g}" y="{y + LINE_H * 0.8:g}" textLength="{n * CHAR_W:g}" '
        f'lengthAdjust="spacingAndGlyphs">{shade(text)}</text>'
    )


def scene_fx(scene: list[str], scene_cell, art_y: float) -> list[str]:
    """Typing fingers and steam rising from the coffee, both in glyphs."""
    out = []

    # Typing: alternate rows of the hand twitch one cell left/right in an uneven rhythm.
    c0, r0 = scene_cell(SCENE_HAND[0], SCENE_HAND[1])
    c1, r1 = scene_cell(SCENE_HAND[2], SCENE_HAND[3])
    rhythm = [0, 1, 0, 0, 1, 0, 1, 1, 0, 0, 1, 0]  # 1 = fingers down on a key
    for k, r in enumerate(range(r0, r1)):
        seg = scene[r][c0:c1]
        if not seg.strip():
            continue
        shift = 1 if k % 2 else -1
        moved = (seg[1:] + " ") if shift < 0 else (" " + seg[:-1])
        vals = ";".join(str(v) for v in (rhythm[k % 3:] + rhythm[:k % 3]))
        out.append(
            f'<g opacity="0">{cells_text(c0, r, moved, art_y)}'
            f'<animate attributeName="opacity" values="{vals}" calcMode="discrete" dur="1.3s" '
            f'repeatCount="indefinite"/></g>'
        )

    # Steam: three wisps of ( ) ~ glyphs curl upward from the rim and fade out.
    m0, rim = scene_cell(SCENE_MUG[0], SCENE_MUG[1])
    m1, _ = scene_cell(SCENE_MUG[2], SCENE_MUG[1])
    height = 7
    frames = 6
    for w, base in enumerate((m0 + (m1 - m0) // 4, m0 + (m1 - m0) // 2, m0 + 3 * (m1 - m0) // 4)):
        for f in range(frames):
            glyphs = []
            for h in range(1, height + 1):
                phase = (h + f + w * 2) * 0.9
                sway = round(1.2 * math.sin(phase))
                ch = "(" if math.cos(phase) > 0.3 else ")" if math.cos(phase) < -0.3 else "~"
                fade = max(0.15, 1 - h / (height + 1))
                glyphs.append((base + sway, rim - h, ch, fade))
            parts = "".join(
                f'<rect x="{PAD + c * CHAR_W:g}" y="{art_y + r * LINE_H:g}" width="{CHAR_W:g}" '
                f'height="{LINE_H:g}" fill="{BG}" fill-opacity="{a * .8:.2f}"/>'
                f'<text x="{PAD + c * CHAR_W:g}" y="{art_y + r * LINE_H + LINE_H * .8:g}" '
                f'fill="#ffffff" fill-opacity="{a:.2f}">{ch}</text>'
                for c, r, ch, a in glyphs if 0 <= r < len(scene)
            )
            vals = ";".join("1" if i == f else "0" for i in range(frames))
            out.append(
                f'<g opacity="0">{parts}<animate attributeName="opacity" values="{vals}" '
                f'calcMode="discrete" dur="{frames * 0.22:.2f}s" begin="{w * 0.3:.1f}s" '
                f'repeatCount="indefinite"/></g>'
            )
    return out


def build(lines: list[str], to_cell) -> str:
    text_w = COLS * CHAR_W
    w = text_w + 2 * PAD
    art_y = PAD
    h = art_y + len(lines) * LINE_H + PAD
    done = START + (len(lines) - 1) * ROW_DELAY + ROW_DUR  # when the portrait finishes
    font = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:g}" height="{h:g}" viewBox="0 0 {w:g} {h:g}">',
        f'<rect x=".5" y=".5" width="{w - 1:g}" height="{h - 1:g}" rx="10" fill="{BG}" stroke="{BORDER}"/>',
    ]

    if not STATIC:
        out.append("<defs>")
        for i in range(len(lines)):
            y = art_y + i * LINE_H
            begin = START + i * ROW_DELAY
            out.append(
                f'<clipPath id="r{i}"><rect x="{PAD}" y="{y:g}" width="0" height="{LINE_H:g}">'
                f'<animate attributeName="width" from="0" to="{text_w:g}" begin="{begin:.3f}s" '
                f'dur="{ROW_DUR}s" fill="freeze"/></rect></clipPath>'
            )
        out.append("</defs>")

    # One loop: face hold, morph to the scene, scene hold, morph back.
    cycle = FACE_HOLD + 2 * MORPH_DUR + SCENE_HOLD
    out.append("<g>" if STATIC else group([(0, FACE_HOLD)], cycle, done, True))
    out.append(f'<g font-family="{font}" font-size="{FONT_SIZE}" fill="{FG}">')
    for i, line in enumerate(lines):
        baseline = art_y + i * LINE_H + LINE_H * 0.8
        clip = "" if STATIC else f' clip-path="url(#r{i})"'
        out.append(
            f'<text x="{PAD}" y="{baseline:g}" textLength="{text_w:g}" '
            f'lengthAdjust="spacingAndGlyphs"{clip}>{shade(line)}</text>'
        )
    out.append("</g>")

    if not STATIC:
        # A block cursor rides each row's wipe edge, visible only while that row prints.
        out.append(f'<g fill="{CURSOR}">')
        for i in range(len(lines)):
            y = art_y + i * LINE_H + 1
            begin = START + i * ROW_DELAY
            out.append(
                f'<rect x="{PAD}" y="{y:g}" width="{CHAR_W:g}" height="{LINE_H - 2:g}" opacity="0">'
                f'<set attributeName="opacity" to="1" begin="{begin:.3f}s" dur="{ROW_DUR}s"/>'
                f'<animate attributeName="x" from="{PAD}" to="{PAD + text_w:g}" '
                f'begin="{begin:.3f}s" dur="{ROW_DUR}s"/></rect>'
            )
        out.append("</g>")

    out += face_fx(lines, to_cell, art_y, done)
    out.append("</g>")  # end of the face group

    if not STATIC:
        scene, scene_cell = scene_grid(len(lines))
        frames = morph_frames(lines, scene)
        dt = MORPH_DUR / len(frames)
        t_scene = FACE_HOLD + MORPH_DUR
        t_back = t_scene + SCENE_HOLD
        layer = f' font-family="{font}" font-size="{FONT_SIZE}" fill="{FG}"'
        out.append(group([(t_scene, t_back)], cycle, done, False, layer))
        out += grid_text(scene, art_y)
        out += scene_fx(scene, scene_cell, art_y)
        out.append("</g>")
        for j, frame in enumerate(frames):
            windows = [(FACE_HOLD + j * dt, FACE_HOLD + (j + 1) * dt),
                       (t_back + (len(frames) - 1 - j) * dt, t_back + (len(frames) - j) * dt)]
            out.append(group(windows, cycle, done, False, layer))
            out += grid_text(frame, art_y)
            out.append("</g>")


    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    lines, to_cell = load_grid()
    OUT.write_text(build(lines, to_cell), encoding="utf-8")
    print(f"wrote {OUT.name} ({COLS}x{len(lines)} chars)")


if __name__ == "__main__":
    main()
