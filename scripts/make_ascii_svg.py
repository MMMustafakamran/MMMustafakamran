"""Convert the prepped photo into a monochrome ASCII-art SVG that "types" itself in.

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
GAMMA = 1.0  # >1 lightens mid-tones (sparser face), <1 darkens them
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

STATIC = os.environ.get("STATIC") == "1"


def load_grid() -> list[str]:
    img = Image.open(SRC).convert("L")
    arr = np.asarray(img, dtype=np.float32)
    subject = arr < 250  # the prep step composited the background to pure white

    # Crop to the subject (plus a small margin) so the grid isn't spent on empty space.
    ys, xs = np.nonzero(subject)
    m = 6
    y0, y1 = max(ys.min() - m, 0), min(ys.max() + m, arr.shape[0])
    x0, x1 = max(xs.min() - m, 0), min(xs.max() + m, arr.shape[1])
    arr, subject = arr[y0:y1, x0:x1], subject[y0:y1, x0:x1]

    # Stretch the subject's own tonal range to the full ramp; keep the background white.
    lo, hi = np.percentile(arr[subject], [2, 98])
    stretched = ((arr - lo) / max(hi - lo, 1.0) * 255.0).clip(0, 245) ** GAMMA / 245.0 ** (GAMMA - 1)
    arr = np.where(subject, stretched, 255.0)
    img = Image.fromarray(arr.astype(np.uint8), "L")

    # Character cells are taller than wide, so sample fewer rows than columns.
    rows = round(COLS * (img.height / img.width) * (CHAR_W / LINE_H))
    small = np.asarray(img.resize((COLS, rows), Image.Resampling.LANCZOS), dtype=np.float32)
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


def build(lines: list[str]) -> str:
    text_w = COLS * CHAR_W
    w = text_w + 2 * PAD
    h = len(lines) * LINE_H + 2 * PAD
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:g}" height="{h:g}" viewBox="0 0 {w:g} {h:g}">',
        f'<rect x=".5" y=".5" width="{w - 1:g}" height="{h - 1:g}" rx="10" fill="{BG}" stroke="{BORDER}"/>',
    ]
    if not STATIC:
        out.append("<defs>")
        for i in range(len(lines)):
            y = PAD + i * LINE_H
            begin = START + i * ROW_DELAY
            out.append(
                f'<clipPath id="r{i}"><rect x="{PAD}" y="{y:g}" width="0" height="{LINE_H:g}">'
                f'<animate attributeName="width" from="0" to="{text_w:g}" begin="{begin:.3f}s" '
                f'dur="{ROW_DUR}s" fill="freeze"/></rect></clipPath>'
            )
        out.append("</defs>")

    font = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"
    out.append(
        f'<g font-family="{font}" font-size="{FONT_SIZE}" fill="{FG}">'
    )
    for i, line in enumerate(lines):
        baseline = PAD + i * LINE_H + LINE_H * 0.8
        clip = "" if STATIC else f' clip-path="url(#r{i})"'
        out.append(
            f'<text x="{PAD}" y="{baseline:g}" textLength="{text_w:g}" '
            f'lengthAdjust="spacingAndGlyphs"{clip}>{esc(line)}</text>'
        )
    out.append("</g>")

    if not STATIC:
        # A block cursor rides each row's wipe edge, visible only while that row prints.
        out.append(f'<g fill="{CURSOR}">')
        for i in range(len(lines)):
            y = PAD + i * LINE_H + 1
            begin = START + i * ROW_DELAY
            out.append(
                f'<rect x="{PAD}" y="{y:g}" width="{CHAR_W:g}" height="{LINE_H - 2:g}" opacity="0">'
                f'<set attributeName="opacity" to="1" begin="{begin:.3f}s" dur="{ROW_DUR}s"/>'
                f'<animate attributeName="x" from="{PAD}" to="{PAD + text_w:g}" '
                f'begin="{begin:.3f}s" dur="{ROW_DUR}s"/></rect>'
            )
        out.append("</g>")
    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    lines = load_grid()
    OUT.write_text(build(lines), encoding="utf-8")
    print(f"wrote {OUT.name} ({COLS}x{len(lines)} chars)")


if __name__ == "__main__":
    main()
