"""Convert the prepped image into a monochrome ASCII-art SVG that "types" itself in.

Each row is revealed by a left-to-right clip wipe with a block cursor riding the edge,
staggered top to bottom. Plays once and freezes (SMIL, so GitHub's <img> renders it).

Usage: python scripts/make_ascii_svg.py            # writes ascii-portrait.svg
       STATIC=1 python scripts/make_ascii_svg.py   # frozen frame, no animation
"""
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
TITLE_H = 30
FOOT_H = 36
USER_HOST = "mustafa@github"
NAME = "Mustafa Kamran"
BG = "#0d1117"
BAR = "#161b22"
MUTED = "#8b949e"
ACCENT = "#39d353"
BORDER = "#30363d"
FG = "#c9d1d9"
CURSOR = "#39d353"

ROW_DELAY = 0.04  # seconds between row starts
ROW_DUR = 0.35  # seconds for one row's wipe
START = 0.2
PROMPT_CW = 7.2  # character width of the 12px footer prompt
TYPE_CPS = 14  # footer typing speed, characters per second
HOLD = 2.8  # seconds each footer command's output stays up

# Footer commands, cycled forever: (command, output). Edit freely.
FOOTER = [
    ("whoami", "Mustafa Kamran"),
    ("cat now.txt", "building agentic AI apps"),
    ("echo $STACK", "TypeScript · React · Python · AWS"),
    ("uptime", "shipping code since 2022"),
    ("echo $COFFEE", "∞"),
]

# Boxes in source-image pixels (x0, y0, x1, y1), mapped onto the character grid.
EYES = [(355, 430, 425, 480), (505, 425, 575, 478)]
BLINK_EVERY = 2.0  # seconds between blinks

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


def discrete(events: list[tuple[float, float]], cycle: float) -> tuple[str, str]:
    """(time, value) steps within one cycle -> SMIL values/keyTimes for calcMode=discrete."""
    steps: dict[float, float] = {}
    for t, v in events:
        steps[round(min(max(t / cycle, 0), 1), 4)] = v
    steps.setdefault(0.0, events[0][1])
    keys = sorted(steps)
    return ";".join(f"{steps[k]:g}" for k in keys), ";".join(f"{k:g}" for k in keys)


def footer(w: float, foot_y: float, done: float, font: str) -> list[str]:
    """Prompt line that types a command, prints its output, clears, and moves to the next."""
    out = [f'<line x1="{PAD / 2:g}" y1="{foot_y:g}" x2="{w - PAD / 2:g}" y2="{foot_y:g}" stroke="{BORDER}"/>']
    py = foot_y + FOOT_H / 2 + 4
    user, host = USER_HOST.split("@")
    prompt = f"{USER_HOST}:~$ "
    px = PAD + len(prompt) * PROMPT_CW
    out.append(
        f'<text x="{PAD}" y="{py:g}" font-family="{font}" font-size="12" '
        f'textLength="{len(prompt.rstrip()) * PROMPT_CW:g}" lengthAdjust="spacingAndGlyphs">'
        f'<tspan fill="{ACCENT}">{user}@{host}</tspan><tspan fill="{MUTED}">:~$</tspan></text>'
    )

    # Timeline of one full cycle through FOOTER.
    items, t = [], 0.0
    for cmd, result in FOOTER:
        typed = len(cmd) / TYPE_CPS
        items.append((t, cmd, result, typed))
        t += typed + 0.35 + HOLD + 0.3
    cycle = t

    cursor = [(0.0, 0.0)]
    for i, (t0, cmd, result, typed) in enumerate(items):
        width = len(f"{cmd} {result}") * PROMPT_CW
        shown = [(0.0, 0.0)]
        for k in range(len(cmd) + 1):
            shown.append((t0 + k / TYPE_CPS, k * PROMPT_CW))
        shown.append((t0 + typed + 0.35, width))
        shown.append((t0 + typed + 0.35 + HOLD, 0.0))
        cursor += shown[1:]
        attrs = ""
        if not STATIC:
            vals, keys = discrete(shown, cycle)
            out.append(
                f'<clipPath id="f{i}"><rect x="{px:g}" y="{foot_y:g}" width="0" height="{FOOT_H:g}">'
                f'<animate attributeName="width" values="{vals}" keyTimes="{keys}" calcMode="discrete" '
                f'dur="{cycle:.2f}s" begin="{done:.2f}s" repeatCount="indefinite"/></rect></clipPath>'
            )
            attrs = f' clip-path="url(#f{i})"'
        elif i:
            continue  # the static frame shows only the first command
        out.append(
            f'<text x="{px:g}" y="{py:g}" font-family="{font}" font-size="12" fill="{FG}" '
            f'textLength="{width:g}" lengthAdjust="spacingAndGlyphs"{attrs}>{esc(cmd)} '
            f'<tspan fill="#ffffff" font-weight="700">{esc(result)}</tspan></text>'
        )

    # Block cursor follows the typing and blinks the whole time.
    first = len(f"{FOOTER[0][0]} {FOOTER[0][1]}") * PROMPT_CW
    cx = px + 2
    anim = ""
    if STATIC:
        cx += first
    else:
        vals, keys = discrete(cursor, cycle)
        xs = ";".join(f"{float(v) + cx:g}" for v in vals.split(";"))
        anim = (
            f'<set attributeName="opacity" to="1" begin="{done:.2f}s"/>'
            f'<animate attributeName="x" values="{xs}" keyTimes="{keys}" calcMode="discrete" '
            f'dur="{cycle:.2f}s" begin="{done:.2f}s" repeatCount="indefinite"/>'
            f'<animate attributeName="fill-opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur="1.1s" '
            f'begin="{done:.2f}s" repeatCount="indefinite"/>'
        )
    hidden = "" if STATIC else ' opacity="0"'
    out.append(f'<rect x="{cx:g}" y="{py - 11:g}" width="7.5" height="14" fill="{FG}"{hidden}>{anim}</rect>')
    return out


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


def scene_grid(n_rows: int) -> list[str]:
    """The second art on the same COLS x n_rows grid as the face, centred."""
    cols = COLS
    while True:
        lines, _ = load_grid(SCENE_SRC, 1.0, cols)
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
    return [
        "".join("*" if ch in "@%" and c >= x0 and r >= y0 else ch for c, ch in enumerate(line))
        for r, line in enumerate(grid)
    ]


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


def build(lines: list[str], to_cell) -> str:
    text_w = COLS * CHAR_W
    w = text_w + 2 * PAD
    art_y = TITLE_H + PAD
    foot_y = art_y + len(lines) * LINE_H + PAD * 0.6
    h = foot_y + FOOT_H
    done = START + (len(lines) - 1) * ROW_DELAY + ROW_DUR  # when the portrait finishes
    font = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:g}" height="{h:g}" viewBox="0 0 {w:g} {h:g}">',
        f'<rect x=".5" y=".5" width="{w - 1:g}" height="{h - 1:g}" rx="10" fill="{BG}" stroke="{BORDER}"/>',
        # Terminal title bar.
        f'<path d="M.5 {TITLE_H}V10.5a10 10 0 0 1 10-10h{w - 21:g}a10 10 0 0 1 10 10V{TITLE_H}z" fill="{BAR}"/>',
        f'<line x1=".5" y1="{TITLE_H}" x2="{w - .5:g}" y2="{TITLE_H}" stroke="{BORDER}"/>',
    ]
    for i, c in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        out.append(f'<circle cx="{18 + i * 16}" cy="{TITLE_H / 2}" r="5" fill="{c}"/>')
    out.append(
        f'<text x="{w / 2:g}" y="{TITLE_H / 2 + 4}" text-anchor="middle" font-family="{font}" '
        f'font-size="11" fill="{MUTED}">{USER_HOST}: ~ ./portrait.sh</text>'
    )

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
        scene = scene_grid(len(lines))
        frames = morph_frames(lines, scene)
        dt = MORPH_DUR / len(frames)
        t_scene = FACE_HOLD + MORPH_DUR
        t_back = t_scene + SCENE_HOLD
        layer = f' font-family="{font}" font-size="{FONT_SIZE}" fill="{FG}"'
        out.append(group([(t_scene, t_back)], cycle, done, False, layer))
        out += grid_text(scene, art_y)
        out.append("</g>")
        for j, frame in enumerate(frames):
            windows = [(FACE_HOLD + j * dt, FACE_HOLD + (j + 1) * dt),
                       (t_back + (len(frames) - 1 - j) * dt, t_back + (len(frames) - j) * dt)]
            out.append(group(windows, cycle, done, False, layer))
            out += grid_text(frame, art_y)
            out.append("</g>")

    out += footer(w, foot_y, done, font)

    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    lines, to_cell = load_grid()
    OUT.write_text(build(lines, to_cell), encoding="utf-8")
    print(f"wrote {OUT.name} ({COLS}x{len(lines)} chars)")


if __name__ == "__main__":
    main()
