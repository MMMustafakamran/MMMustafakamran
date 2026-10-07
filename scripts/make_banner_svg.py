"""Banner: your name prints in big block letters with a green shimmer sweeping across it
on repeat, then a tagline types out underneath.

The block letters come from scripts/name-art.txt (figlet "ANSI Shadow" output), drawn as
shapes rather than text so they look identical in every browser. To change the text:
    pip install pyfiglet && python -c "import pyfiglet; print(pyfiglet.figlet_format('YOUR NAME', font='ansi_shadow', width=300))" > scripts/name-art.txt

Usage: python scripts/make_banner_svg.py           # writes banner.svg
       STATIC=1 python scripts/make_banner_svg.py  # frozen frame, no animation
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ART = Path(__file__).with_name("name-art.txt")
OUT = ROOT / "banner.svg"

USER_HOST = "mustafa@github"
TAGLINE = "Fullstack Developer · AI Engineer · Cloud Architect"

W = 860
PAD = 24
TITLE_H = 30
FONT_SIZE = 13
CW = 7.8  # forced character width at FONT_SIZE
LINE_H = 21

BG = "#0d1117"
BAR = "#161b22"
BORDER = "#30363d"
FG = "#c9d1d9"
MUTED = "#8b949e"
ACCENT = "#39d353"
BLOCK = "#26a641"
SHADOW = "#0e4429"
SHINE = "#d2ffe4"

SHIMMER_EVERY = 3.8  # seconds per shimmer pass over the name
TYPE_CPS = 24
STATIC = os.environ.get("STATIC") == "1"
FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def art_shapes(art: list[str], x0: float, y0: float, cw: float, ch: float) -> tuple[str, str]:
    """Return (block rects, shadow paths) for figlet ANSI Shadow art."""
    rects, path = [], []
    for r, row in enumerate(art):
        y = y0 + r * ch
        c = 0
        while c < len(row):
            if row[c] == "█":
                start = c
                while c < len(row) and row[c] == "█":
                    c += 1
                rects.append(f'<rect x="{x0 + start * cw:.2f}" y="{y:.2f}" width="{(c - start) * cw + .3:.2f}" height="{ch + .3:.2f}"/>')
                continue
            ch_ = row[c]
            if ch_ in "═║╔╗╚╝":
                # Double lines through the cell, like the box-drawing glyph.
                cx, cy, d = x0 + c * cw + cw / 2, y + ch / 2, 1.3
                left, right, top, bot = x0 + c * cw, x0 + (c + 1) * cw, y, y + ch
                if ch_ == "═":
                    path += [f"M{left:.2f} {cy - d:.2f}H{right:.2f}", f"M{left:.2f} {cy + d:.2f}H{right:.2f}"]
                elif ch_ == "║":
                    path += [f"M{cx - d:.2f} {top:.2f}V{bot:.2f}", f"M{cx + d:.2f} {top:.2f}V{bot:.2f}"]
                else:
                    h_to = right if ch_ in "╔╚" else left
                    v_to = bot if ch_ in "╔╗" else top
                    for k in (-d, d):
                        # Nested corners: outer and inner strokes.
                        sx = k if ch_ in "╔╚" else -k
                        sy = k if ch_ in "╔╗" else -k
                        path.append(f"M{h_to:.2f} {cy + sy:.2f}H{cx + sx:.2f}V{v_to:.2f}")
            c += 1
    return "".join(rects), "".join(path)


def build() -> str:
    art = [l.rstrip("\n") for l in ART.read_text(encoding="utf-8").splitlines() if l.strip()]
    cols = max(map(len, art))
    cw = (W - 2 * PAD) / cols
    ch = cw * 2.0

    art_y = TITLE_H + PAD + 4
    tag_y = art_y + len(art) * ch + 30
    h = round(tag_y + PAD - 2)

    t_art = 0.3
    t_tag = t_art + 1.0

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}">',
        "<style>",
        f"text{{font-family:{FONT};font-size:{FONT_SIZE}px;fill:{FG};white-space:pre}}",
        f".m{{fill:{MUTED}}} .ok{{fill:{ACCENT};font-weight:700}} .a{{fill:{ACCENT}}}",
        "</style>",
        f'<rect x=".5" y=".5" width="{W - 1}" height="{h - 1}" rx="10" fill="{BG}" stroke="{BORDER}"/>',
        f'<path d="M.5 {TITLE_H}V10.5a10 10 0 0 1 10-10h{W - 21}a10 10 0 0 1 10 10V{TITLE_H}z" fill="{BAR}"/>',
        f'<line x1=".5" y1="{TITLE_H}" x2="{W - .5}" y2="{TITLE_H}" stroke="{BORDER}"/>',
    ]
    for i, c in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        out.append(f'<circle cx="{18 + i * 16}" cy="{TITLE_H / 2}" r="5" fill="{c}"/>')
    out.append(
        f'<text x="{W / 2}" y="{TITLE_H / 2 + 4}" text-anchor="middle" class="m" style="font-size:11px">'
        f"{USER_HOST}: ~</text>"
    )

    def show(t: float) -> tuple[str, str]:
        """(opening attrs, child <set>) to make an element appear at time t."""
        if STATIC:
            return "", ""
        return ' opacity="0"', f'<set attributeName="opacity" to="1" begin="{t:.2f}s"/>'

    def hide(t: float) -> str:
        return "" if STATIC else f'<set attributeName="opacity" to="0" begin="{t:.2f}s"/>'

    # Name in block letters, wiped in left to right, then a shimmer sweeps across on repeat.
    blocks, shadow = art_shapes(art, PAD, art_y, cw, ch)
    art_w = cols * cw
    defs = [
        "<defs>",
        f'<linearGradient id="shine" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="{W}" y2="0" '
        f'gradientTransform="translate({-W} 0)">'
        f'<stop offset="0" stop-color="{BLOCK}"/><stop offset=".42" stop-color="{BLOCK}"/>'
        f'<stop offset=".5" stop-color="{SHINE}"/><stop offset=".58" stop-color="{BLOCK}"/>'
        f'<stop offset="1" stop-color="{BLOCK}"/>'
    ]
    if not STATIC:
        defs.append(
            f'<animateTransform attributeName="gradientTransform" type="translate" '
            f'values="{-W:g} 0;{W:g} 0;{W:g} 0" keyTimes="0;.55;1" dur="{SHIMMER_EVERY}s" '
            f'begin="{t_art + .9:.2f}s" repeatCount="indefinite"/>'
        )
    defs.append("</linearGradient>")
    if not STATIC:
        defs.append(
            f'<clipPath id="wipe"><rect x="{PAD}" y="{art_y - 4:g}" width="0" height="{len(art) * ch + 8:g}">'
            f'<animate attributeName="width" from="0" to="{art_w + 4:g}" begin="{t_art:.2f}s" dur=".9s" '
            f'fill="freeze"/></rect></clipPath>'
        )
    defs.append("</defs>")
    out += defs
    clip = "" if STATIC else ' clip-path="url(#wipe)"'
    # The gradient starts translated off to the left, so the shine band is parked outside the
    # letters until the shimmer runs (and stays there in the static frame).
    out.append(
        f'<g{clip}><path d="{shadow}" fill="none" stroke="{SHADOW}" stroke-width="1.1"/>'
        f'<g fill="url(#shine)">{blocks}</g></g>'
    )

    # Tagline typed under the name, then a blinking cursor.
    tag = f"> {TAGLINE}"
    ty = tag_y
    if STATIC:
        out.append(f'<text x="{PAD}" y="{ty:g}" textLength="{len(tag) * CW:g}" lengthAdjust="spacingAndGlyphs">'
                   f'<tspan class="a">&gt;</tspan>{esc(tag[1:])}</text>')
    else:
        steps = ";".join(f"{k * CW:g}" for k in range(len(tag) + 1))
        out.append(
            f'<clipPath id="tag"><rect x="{PAD}" y="{ty - FONT_SIZE - 2:g}" width="0" height="{LINE_H}">'
            f'<animate attributeName="width" values="{steps}" calcMode="discrete" begin="{t_tag:.2f}s" '
            f'dur="{len(tag) / TYPE_CPS:.2f}s" fill="freeze"/></rect></clipPath>'
        )
        out.append(
            f'<text x="{PAD}" y="{ty:g}" textLength="{len(tag) * CW:g}" lengthAdjust="spacingAndGlyphs" '
            f'clip-path="url(#tag)"><tspan class="a">&gt;</tspan>{esc(tag[1:])}</text>'
        )
    cx = PAD + (len(tag) + 1) * CW
    a, s = show(t_tag + len(tag) / TYPE_CPS)
    blink = "" if STATIC else (
        f'<animate attributeName="fill-opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur="1.1s" '
        f'begin="{t_tag:.2f}s" repeatCount="indefinite"/>'
    )
    out.append(f'<rect x="{cx:g}" y="{ty - FONT_SIZE + 1:g}" width="8" height="{FONT_SIZE + 2}" fill="{ACCENT}"{a}>{s}{blink}</rect>')

    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT.name}")


if __name__ == "__main__":
    main()
