"""Convert the prepped image into a monochrome ASCII-art SVG that "types" itself in.

Each row is revealed by a left-to-right clip wipe with a block cursor riding the edge,
staggered top to bottom. Plays once and freezes (SMIL, so GitHub's <img> renders it).

Usage: python scripts/make_ascii_svg.py            # writes ascii-portrait.svg
       STATIC=1 python scripts/make_ascii_svg.py   # frozen frame, no animation
"""
import os
import random
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source-prepped.png"
OUT = ROOT / "ascii-portrait.svg"

RAMP = " .`:-=+*cs#%@"  # bright (sparse) -> dark (dense); leading space clears the background
COLS = 120
SHADES = [".55", ".6", ".78", "1"]  # glyph opacity per density band, sparse -> dense
HAIR_MAX = 70  # cells darker than this (0-255) can count as hair for the shimmer
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
LENSES = [(330, 410, 465, 525), (495, 405, 640, 522)]
MOUTH = (395, 590, 555, 612)
BLINK_EVERY = 3.0  # seconds between blinks
GLINT_EVERY = 5.0  # seconds between `/` streaks across the lenses
SHIMMER_EVERY = 6.0  # seconds between glyph waves through the hair
SMILE_EVERY = 7.0  # seconds between grins
RAIN_COLS = 16  # falling glyph columns in the empty space
RAIN_GLYPHS = "01:.<>/|+=*"

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


def load_grid() -> tuple[list[str], callable, np.ndarray]:
    img = Image.open(SRC).convert("L")
    arr = np.asarray(img, dtype=np.float32)
    subject = arr < 250  # the prep step composited the background to pure white

    # Crop to the subject (plus a small margin) so the grid isn't spent on empty space.
    ys, xs = np.nonzero(subject)
    m = 6
    y0, y1 = max(ys.min() - m, 0), min(ys.max() + m, arr.shape[0])
    x0, x1 = max(xs.min() - m, 0), min(xs.max() + m, arr.shape[1])
    y1 = y0 + round((y1 - y0) * CROP_BOTTOM)
    arr, subject = arr[y0:y1, x0:x1], subject[y0:y1, x0:x1]

    # Stretch the subject's own tonal range to the full ramp; keep the background white.
    lo, hi = np.percentile(arr[subject], [2, 98])
    stretched = ((arr - lo) / max(hi - lo, 1.0) * 255.0).clip(0, 245) ** GAMMA / 245.0 ** (GAMMA - 1)
    arr = np.where(subject, stretched, 255.0)

    # Character cells are taller than wide, so sample fewer rows than columns.
    rows = round(COLS * (arr.shape[0] / arr.shape[1]) * (CHAR_W / LINE_H))
    img = Image.fromarray(arr.astype(np.uint8), "L")
    small = np.asarray(img.resize((COLS, rows), Image.Resampling.BOX), dtype=np.float32)
    if LINE_WEIGHT:
        # Thin dark outlines vanish when a whole cell is averaged; mix in each cell's darkest
        # pixel so line art (glasses, eyes, jaw) survives the downsample.
        small = small * (1 - LINE_WEIGHT) + dark_pool(arr, COLS, rows) * LINE_WEIGHT
    if POSITIVE:
        # Light text on a dark terminal: bright areas print dense, so it reads like the
        # original. The subject's darkest areas still get a faint glyph (not a space)
        # so dark hair keeps its silhouette.
        mask = np.asarray(Image.fromarray(subject.astype(np.uint8) * 255).resize((COLS, rows), Image.Resampling.BOX))
        idx = 2 + (small / 256.0 * (len(RAMP) - 2)).astype(int).clip(0, len(RAMP) - 3)
        idx = np.where(mask > 127, idx, 0)
        # Hair = large dark areas of the subject. Opening drops 1-cell-wide outlines
        # (jaw, glasses, nose) so the hair shimmer stays on the hair.
        hair = ((mask > 127) & (small < HAIR_MAX)).astype(np.uint8)
        hair = cv2.morphologyEx(hair, cv2.MORPH_OPEN, np.ones((2, 3), np.uint8)).astype(bool)
    else:
        idx = ((255.0 - small) / 256.0 * len(RAMP)).astype(int).clip(0, len(RAMP) - 1)
        hair = np.zeros(idx.shape, bool)
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
        col = (x - x0) / (x1 - x0) * COLS
        row = (y - y0) / (y1 - y0) * rows - top
        return round(col), round(row)

    return lines, to_cell, hair[top:top + len(lines)]


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
            band = bands - 1  # effect glyphs (/ \ etc.) print at full brightness
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


def cells_text(x_col: int, row: int, text: str, art_y: float, cls: str = "") -> str:
    """A run of glyphs placed exactly on the grid, with a background patch under it."""
    x = PAD + x_col * CHAR_W
    y = art_y + row * LINE_H
    n = len(text)
    c = f' class="{cls}"' if cls else ""
    return (
        f'<rect x="{x:g}" y="{y:g}" width="{n * CHAR_W:g}" height="{LINE_H:g}" fill="{BG}"/>'
        f'<text{c} x="{x:g}" y="{y + LINE_H * 0.8:g}" textLength="{n * CHAR_W:g}" '
        f'lengthAdjust="spacingAndGlyphs">{shade(text)}</text>'
    )


def bump(ch: str, k: int) -> str:
    """Same cell, k steps denser/brighter on the ramp."""
    if ch == " ":
        return ch
    return RAMP[min(RAMP.index(ch) + k, len(RAMP) - 1)]


def sweep_clip(cid: str, x0: float, x1: float, y: float, win: float, begin: float,
               move: float, every: float) -> str:
    """A window `win` wide that slides from x0 to x1 in `move` s, repeating every `every` s."""
    frac = move / every
    return (
        f'<clipPath id="{cid}"><rect x="{x0 - win:g}" y="{y:g}" width="{win:g}" height="{LINE_H:g}">'
        f'<animate attributeName="x" values="{x0 - win:g};{x1:g};{x1:g}" keyTimes="0;{frac:.3f};1" '
        f'dur="{every}s" begin="{begin:.3f}s" repeatCount="indefinite"/></rect></clipPath>'
    )


def hair_shimmer(lines: list[str], hair, art_y: float, done: float) -> list[str]:
    """A diagonal wave runs through the hair; glyphs it passes step up the ramp, then settle."""
    text_w = COLS * CHAR_W
    move = 1.4
    speed = (text_w + 60) / move
    row_lag = LINE_H / speed  # one row lower = starts later -> a slanted wave front
    layers = [(1, 12), (4, 4)]  # (ramp boost, window width in cells): soft halo, bright core
    defs, body = [], []
    for r, line in enumerate(lines):
        cols = [c for c in range(len(line)) if hair[r][c]]
        if not cols:
            continue
        lo, hi = min(cols), max(cols) + 1
        begin = done + 1.2 + r * row_lag
        for li, (boost, win) in enumerate(layers):
            seg = "".join(bump(line[c], boost) if hair[r][c] else line[c] for c in range(lo, hi))
            cid = f"hs{li}_{r}"
            # The core trails the halo's centre so the brightest glyphs sit mid-wave.
            lag = (layers[0][1] - win) / 2 * CHAR_W / speed
            defs.append(sweep_clip(cid, PAD, PAD + text_w, art_y + r * LINE_H, win * CHAR_W,
                                   begin + lag, move, SHIMMER_EVERY))
            body.append(f'<g clip-path="url(#{cid})">{cells_text(lo, r, seg, art_y)}</g>')
    return ["<defs>", *defs, "</defs>", *body]


def lens_glint(lines: list[str], to_cell, art_y: float, done: float) -> list[str]:
    """A `/` streak of bright glyphs steps across each lens."""
    defs, body = [], []
    move = 0.45
    for i, (bx0, by0, bx1, by1) in enumerate(LENSES):
        c0, r0 = to_cell(bx0, by0)
        c1, r1 = to_cell(bx1, by1)
        width = (c1 - c0) * CHAR_W
        speed = (width + 2 * CHAR_W) / move
        for r in range(max(r0, 0), min(r1, len(lines))):
            # Lower rows start later by one cell's travel, so the streak leans like "/".
            begin = done + 2.0 + i * 0.3 + (r - r0) * CHAR_W / speed
            cid = f"gl{i}_{r}"
            defs.append(sweep_clip(cid, PAD + c0 * CHAR_W, PAD + c1 * CHAR_W, art_y + r * LINE_H,
                                   2 * CHAR_W, begin, move, GLINT_EVERY))
            body.append(f'<g clip-path="url(#{cid})">{cells_text(c0, r, "/" * (c1 - c0), art_y, "hi")}</g>')
    return ["<defs>", *defs, "</defs>", *body]


def grin(lines: list[str], to_cell, art_y: float, done: float) -> list[str]:
    """Now and then the smile line widens into an open grin for a moment."""
    c0, r0 = to_cell(MOUTH[0], MOUTH[1])
    c1, r1 = to_cell(MOUTH[2], MOUTH[3])
    rows = range(max(r0, 0), min(r1 + 1, len(lines)))
    # The smile is the row inside the box with the longest run of "-"/"=" glyphs.
    def run(r: int) -> tuple[int, int, int]:
        best = (0, 0, 0)
        c = c0
        while c < c1:
            if lines[r][c] in "-=":
                s = c
                while c < c1 and lines[r][c] in "-=":
                    c += 1
                best = max(best, (c - s, s, c))
            c += 1
        return best
    rm = max(rows, key=lambda r: run(r)[0])
    _, lo, hi = run(rm)
    top = "\\" + "#" * (hi - lo + 2) + "/"
    bottom = "\\" + "=" * max(hi - lo - 4, 2) + "/"
    on = 0.7 / SMILE_EVERY
    return [
        f'<g opacity="0">{cells_text(lo - 2, rm, top, art_y)}'
        f'{cells_text(lo + 1, rm + 1, bottom, art_y)}'
        f'<animate attributeName="opacity" values="0;1;0" keyTimes="0;{1 - on:.3f};1" calcMode="discrete" '
        f'dur="{SMILE_EVERY}s" begin="{done + 2.6:.2f}s" repeatCount="indefinite"/></g>'
    ]


def rain(lines: list[str], art_y: float, done: float) -> list[str]:
    """Faint falling columns of glyphs in the empty space around the portrait, never over it."""
    rng = random.Random(7)  # fixed seed: same output every run
    n_rows = len(lines)
    free = [c for c in range(COLS) if sum(line[c] == " " for line in lines) >= n_rows * 0.45]
    picks: list[int] = []
    for c in rng.sample(free, len(free)):
        if all(abs(c - p) >= 3 for p in picks):
            picks.append(c)
        if len(picks) == RAIN_COLS:
            break
    trail = 9 * LINE_H
    defs = [
        "<defs>",
        '<linearGradient id="trail" x1="0" x2="0" y1="0" y2="1">'
        '<stop offset="0" stop-color="#000"/><stop offset=".85" stop-color="#fff" stop-opacity=".9"/>'
        '<stop offset="1" stop-color="#fff"/></linearGradient>',
    ]
    body = []
    top, bottom = art_y - trail, art_y + n_rows * LINE_H
    for i, c in enumerate(sorted(picks)):
        x = PAD + c * CHAR_W
        glyphs = "".join(
            f'<tspan x="{x:g}" y="{art_y + r * LINE_H + LINE_H * 0.8:g}">{esc(rng.choice(RAIN_GLYPHS))}</tspan>'
            for r in range(n_rows) if lines[r][c] == " "
        )
        dur = rng.uniform(3.2, 6.0)
        begin = done + rng.uniform(0, dur)
        defs.append(
            f'<mask id="rm{i}"><rect x="{x - 1:g}" y="{top:g}" width="{CHAR_W + 2:g}" height="{trail:g}" fill="url(#trail)">'
            f'<animate attributeName="y" values="{top:g};{bottom:g}" dur="{dur:.2f}s" begin="{begin:.2f}s" '
            f'repeatCount="indefinite"/></rect></mask>'
        )
        body.append(f'<text mask="url(#rm{i})" class="rain">{glyphs}</text>')
    defs.append("</defs>")
    return defs + body


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


def build(lines: list[str], to_cell, hair) -> str:
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
        f"<style>.hi{{fill:#fff}} .rain{{fill:{ACCENT};fill-opacity:.4}}</style>",
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

    if not STATIC:
        out.append(f'<g font-family="{font}" font-size="{FONT_SIZE}">')
        out += rain(lines, art_y, done)
        out.append("</g>")
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

    if not STATIC:
        out.append(f'<g font-family="{font}" font-size="{FONT_SIZE}" fill="{FG}">')
        out += hair_shimmer(lines, hair, art_y, done)
        out += lens_glint(lines, to_cell, art_y, done)
        out += grin(lines, to_cell, art_y, done)
        out.append("</g>")
    out += face_fx(lines, to_cell, art_y, done)
    out += footer(w, foot_y, done, font)

    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    lines, to_cell, hair = load_grid()
    OUT.write_text(build(lines, to_cell, hair), encoding="utf-8")
    print(f"wrote {OUT.name} ({COLS}x{len(lines)} chars)")


if __name__ == "__main__":
    main()
