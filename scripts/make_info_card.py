"""Hand-authored neofetch-style info card SVG.

Edit CARD below, then: python scripts/make_info_card.py   # writes info-card.svg
STATIC=1 emits a frozen frame (no animation) for local previews.
"""
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "info-card.svg"
PORTRAIT = ROOT / "ascii-portrait.svg"

USER_HOST = "mustafa@github"

# (key, value) rows. A list value prints one item per line under the same key.
# An empty key with value "" leaves a blank spacer line.
CARD = [
    ("Name", "Mustafa Kamran"),
    ("Role", "Fullstack Developer · AI Engineer · Cloud"),
    ("Now", "TODO: current role @ company"),
    ("Prev", "TODO: previous role @ company"),
    ("", ""),
    ("Web", "TypeScript · React · Next.js · Node · GraphQL"),
    ("AI/ML", "Python · PyTorch · TensorFlow · LLMs · RAG"),
    ("Cloud", "AWS · Azure · GCP · Docker · Kubernetes"),
    ("", ""),
    ("Highlights", [
        "TODO: shipped something you're proud of",
        "TODO: a number that tells the story",
        "TODO: an award, talk, or open-source win",
    ]),
    ("", ""),
    ("Site", "mustafakamran.vercel.app"),
    ("Email", "mmmustafakamran@gmail.com"),
]

# Display widths in README.md; used to make this card's rendered height match the portrait's.
PORTRAIT_DISPLAY_W = 370
CARD_DISPLAY_W = 490

W = 640
PAD_X = 28
TITLE_H = 34
FONT_SIZE = 14
LINE_H = 23
KEY_COL = 12  # characters reserved for "Key:" column

BG = "#0d1117"
BAR = "#161b22"
BORDER = "#30363d"
FG = "#c9d1d9"
MUTED = "#8b949e"
ACCENT = "#39d353"
KEY = "#58a6ff"
TODO = "#d29922"
SWATCHES = ["#0d1117", "#f85149", "#39d353", "#d29922", "#58a6ff", "#bc8cff", "#39c5cf", "#c9d1d9"]

STAGGER = 0.09
START = 0.3
STATIC = os.environ.get("STATIC") == "1"


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def card_height() -> float:
    """Match the portrait's on-page height when both are shown side by side."""
    try:
        head = PORTRAIT.read_text(encoding="utf-8")[:300]
        pw, ph = (float(v) for v in re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', head).groups())
        return round(ph * PORTRAIT_DISPLAY_W / pw * W / CARD_DISPLAY_W)
    except (OSError, AttributeError):
        return 460


def lines() -> list[tuple[str, str]]:
    """Flatten CARD to (key, value) display lines."""
    out = []
    for key, value in CARD:
        if isinstance(value, list):
            for i, item in enumerate(value):
                out.append((key if i == 0 else "", "▸ " + item))
        else:
            out.append((key, value))
    return out


def build() -> str:
    rows = lines()
    char_w = FONT_SIZE * 0.6
    val_x = PAD_X + KEY_COL * char_w

    # Lay out the body first; the card's height depends on where it ends.
    body = []
    y = TITLE_H + 34
    n = 0

    def line(content: str) -> None:
        nonlocal y, n
        style = "" if STATIC else f' style="animation-delay:{START + n * STAGGER:.2f}s"'
        body.append(f'<g class="ln"{style}>{content}</g>')
        y += LINE_H
        n += 1

    user, host = USER_HOST.split("@")
    line(f'<text x="{PAD_X}" y="{y}"><tspan class="a">{user}</tspan>'
         f'<tspan class="m">@</tspan><tspan class="a">{host}</tspan></text>')
    line(f'<text x="{PAD_X}" y="{y}" class="m">{"-" * len(USER_HOST)}</text>')
    for key, value in rows:
        if not key and not value:
            y += LINE_H * 0.5
            continue
        cls = ' class="t"' if "TODO" in value else ""
        key_el = f'<text x="{PAD_X}" y="{y}" class="k">{esc(key)}:</text>' if key else ""
        line(f'{key_el}<text x="{val_x:g}" y="{y}"{cls}>{esc(value)}</text>')

    y += LINE_H * 0.4
    sw = 26
    blocks = "".join(
        f'<rect x="{PAD_X + i * sw}" y="{y - 14:g}" width="{sw}" height="16" fill="{c}"/>'
        for i, c in enumerate(SWATCHES)
    )
    line(f'<g>{blocks}<rect x="{PAD_X}" y="{y - 14:g}" width="{sw * len(SWATCHES)}" height="16" '
         f'fill="none" stroke="{BORDER}"/></g>')

    target = card_height()
    h = max(target, round(y - LINE_H + 24))
    if h > target:
        print(f"note: card content needs {h}px but the portrait matches {target}px; "
              "trim CARD or lower LINE_H to keep the columns level")

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}">',
        "<style>",
        "text{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace;"
        f"font-size:{FONT_SIZE}px;fill:{FG};white-space:pre}}",
        f".k{{fill:{KEY};font-weight:700}} .m{{fill:{MUTED}}} .a{{fill:{ACCENT};font-weight:700}}"
        f" .t{{fill:{TODO}}}",
    ]
    if not STATIC:
        out += [
            ".ln{opacity:0;animation:in .45s ease-out forwards}",
            "@keyframes in{from{opacity:0;transform:translateX(-8px)}to{opacity:1;transform:none}}",
        ]
    out += [
        "</style>",
        f'<rect x=".5" y=".5" width="{W - 1}" height="{h - 1}" rx="10" fill="{BG}" stroke="{BORDER}"/>',
        f'<path d="M.5 {TITLE_H}V10.5a10 10 0 0 1 10-10h{W - 21}a10 10 0 0 1 10 10V{TITLE_H}z" fill="{BAR}"/>',
        f'<line x1=".5" y1="{TITLE_H}" x2="{W - .5}" y2="{TITLE_H}" stroke="{BORDER}"/>',
    ]
    for i, c in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        out.append(f'<circle cx="{20 + i * 18}" cy="{TITLE_H / 2}" r="5.5" fill="{c}"/>')
    out.append(
        f'<text x="{W / 2}" y="{TITLE_H / 2 + 4.5}" text-anchor="middle" class="m" '
        f'style="font-size:12px">{USER_HOST} — neofetch</text>'
    )
    out += body
    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT.name}")


if __name__ == "__main__":
    main()
