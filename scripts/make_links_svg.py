"""Link chips: one small terminal-style SVG per link, written to links/<name>.svg.

Each chip is its own image because a README can only make a whole image clickable. The
URLs live in README.md; this only draws the labels.

Usage: python scripts/make_links_svg.py           # writes links/*.svg
       STATIC=1 python scripts/make_links_svg.py  # no fade-in
"""
import os
from pathlib import Path

from theme import ACCENT, BORDER, FG_BRIGHT, FONT, MUTED, TILE

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "links"

LINKS = ["portfolio", "linkedin", "email"]

FONT_SIZE = 13
CW = 7.8  # forced character width at FONT_SIZE
PAD_X = 16
H = 38
STATIC = os.environ.get("STATIC") == "1"


def build(label: str, order: int) -> str:
    text = f"~/{label}"
    arrow_x = PAD_X + (len(text) + 1) * CW
    w = round(arrow_x + CW + PAD_X)
    y = H / 2 + 4.5
    css = [f"text{{font-family:{FONT};font-size:{FONT_SIZE}px;fill:{FG_BRIGHT}}}"]
    if not STATIC:
        css += [
            f"svg>*{{opacity:0;animation:in .5s ease-out {0.2 + order * 0.12:.2f}s forwards}}",
            "@keyframes in{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}",
            "@media (prefers-reduced-motion:reduce){svg>*{animation:none;opacity:1}}",
        ]
    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{H}" viewBox="0 0 {w} {H}">',
        "<style>", *css, "</style>",
        f'<rect x=".5" y=".5" width="{w - 1}" height="{H - 1}" rx="8" fill="{TILE}" stroke="{BORDER}"/>',
        f'<text x="{PAD_X}" y="{y:g}" textLength="{len(text) * CW:g}" lengthAdjust="spacingAndGlyphs">'
        f'<tspan fill="{ACCENT}">~/</tspan>{label}</text>',
        # Arrow drawn as a path so it does not depend on the font having the glyph.
        f'<path d="M{arrow_x:g} {y - 1:g}l7 -7m-5.5 0h5.5v5.5" fill="none" stroke="{MUTED}" '
        'stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>',
        "</svg>",
    ])


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for i, label in enumerate(LINKS):
        (OUT / f"{label}.svg").write_text(build(label, i), encoding="utf-8")
        print(f"wrote links/{label}.svg")


if __name__ == "__main__":
    main()
