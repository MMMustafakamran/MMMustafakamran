"""Convert the prepped image into a monochrome ASCII-art SVG that "types" itself in.

Each row is revealed by a left-to-right clip wipe with a block cursor riding the edge,
staggered top to bottom. Plays once and freezes (SMIL, so GitHub's <img> renders it).

Usage: python scripts/make_ascii_svg.py            # writes ascii-portrait.svg
       STATIC=1 python scripts/make_ascii_svg.py   # frozen frame, no animation
"""
import os
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source-prepped.png"
OUT = ROOT / "ascii-portrait.svg"

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
TYPE_DUR = 1.2  # seconds to type the footer prompt

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


def load_grid() -> list[str]:
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
    else:
        idx = ((255.0 - small) / 256.0 * len(RAMP)).astype(int).clip(0, len(RAMP) - 1)
    lines = ["".join(RAMP[i] for i in row) for row in idx]
    # Trim blank rows top and bottom so the portrait sits snug in its frame.
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


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
        band = None if ch == " " else min(RAMP.index(ch) * bands // len(RAMP), bands - 1)
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


def build(lines: list[str]) -> str:
    text_w = COLS * CHAR_W
    w = text_w + 2 * PAD
    art_y = TITLE_H + PAD
    foot_y = art_y + len(lines) * LINE_H + PAD * 0.6
    h = foot_y + FOOT_H
    done = START + (len(lines) - 1) * ROW_DELAY + ROW_DUR  # when the portrait finishes
    font = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"
    prompt_text = f"{USER_HOST}:~$ whoami {NAME}"

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
        # Reveal the prompt one character at a time.
        steps = ";".join(f"{k * PROMPT_CW:g}" for k in range(len(prompt_text) + 1))
        out.append(
            f'<clipPath id="prompt"><rect x="{PAD}" y="{foot_y:g}" width="0" height="{FOOT_H:g}">'
            f'<animate attributeName="width" values="{steps}" calcMode="discrete" begin="{done:.2f}s" '
            f'dur="{TYPE_DUR}s" fill="freeze"/></rect></clipPath>'
        )
        out.append("</defs>")

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

    # Footer prompt: types "whoami <name>" once the portrait is done, then a cursor blinks forever.
    out.append(f'<line x1="{PAD / 2:g}" y1="{foot_y:g}" x2="{w - PAD / 2:g}" y2="{foot_y:g}" stroke="{BORDER}"/>')
    py = foot_y + FOOT_H / 2 + 4
    user, host = USER_HOST.split("@")
    prompt = (
        f'<tspan fill="{ACCENT}">{user}@{host}</tspan><tspan fill="{MUTED}">:~$ </tspan>'
        f'<tspan fill="{FG}">whoami </tspan><tspan fill="#ffffff" font-weight="700">{esc(NAME)}</tspan>'
    )
    clip = "" if STATIC else ' clip-path="url(#prompt)"'
    out.append(
        f'<text x="{PAD}" y="{py:g}" font-family="{font}" font-size="12" fill="{FG}" '
        f'textLength="{len(prompt_text) * PROMPT_CW:g}" lengthAdjust="spacingAndGlyphs"{clip}>{prompt}</text>'
    )
    cx = PAD + (len(prompt_text) + 1) * PROMPT_CW
    typed = done + TYPE_DUR
    blink = "" if STATIC else (
        f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur="1.1s" '
        f'begin="{typed:.2f}s" repeatCount="indefinite"/>'
    )
    hidden = "" if STATIC else ' opacity="0"'
    show = "" if STATIC else f'<set attributeName="opacity" to="1" begin="{typed:.2f}s"/>'
    out.append(f'<rect x="{cx:g}" y="{py - 11:g}" width="7.5" height="14" fill="{FG}"{hidden}>{show}{blink}</rect>')

    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    lines = load_grid()
    OUT.write_text(build(lines), encoding="utf-8")
    print(f"wrote {OUT.name} ({COLS}x{len(lines)} chars)")


if __name__ == "__main__":
    main()
