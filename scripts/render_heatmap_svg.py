"""Render data/contributions.json as an animated 53-week contribution heatmap SVG.

Cells slide in along a diagonal once on load, then freeze (CSS keyframes, no looping).

Usage: python scripts/render_heatmap_svg.py           # writes contrib-heatmap.svg
       STATIC=1 python scripts/render_heatmap_svg.py  # frozen frame, no animation
"""
import json
import os
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "contributions.json"
OUT = ROOT / "contrib-heatmap.svg"

PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]
#          none -> brightest (level 5 is a neon top end for standout days)
BG = "#0d1117"
BORDER = "#30363d"
FG = "#c9d1d9"
MUTED = "#8b949e"
ACCENT = "#39d353"

W = 860
PAD = 24
LABEL_W = 30  # room for Mon/Wed/Fri
TOP = 58  # header + month labels
GAP = 3
FOOT = 40

CELL_DELAY = 0.018  # seconds per diagonal step
START = 0.2
SWEEP_EVERY = 9.0  # seconds between radar sweeps
SWEEP_DUR = 2.6  # seconds for one sweep across the grid
STATIC = os.environ.get("STATIC") == "1"

MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def radar(cells, grid_x, grid_y, pitch, size, ncols, begin) -> list[str]:
    """Looping scan line that lights up the cells it passes, plus a pulsing ring on today."""
    grid_w = ncols * pitch - GAP
    grid_h = 7 * pitch - GAP
    band = 70
    frac = SWEEP_DUR / SWEEP_EVERY
    out = [
        "<defs>",
        '<linearGradient id="sweep" x1="0" x2="1" y1="0" y2="0">'
        f'<stop offset="0" stop-color="{PALETTE[5]}" stop-opacity="0"/>'
        f'<stop offset=".85" stop-color="{PALETTE[5]}" stop-opacity=".55"/>'
        f'<stop offset="1" stop-color="{PALETTE[5]}" stop-opacity="0"/></linearGradient>',
        # The glow only shows through the cells, so the gaps stay dark.
        '<clipPath id="cells">'
        + "".join(
            f'<rect x="{grid_x + c * pitch:.1f}" y="{grid_y + r * pitch:.1f}" width="{size:.1f}" '
            f'height="{size:.1f}" rx="2.5"/>'
            for c, r, _, _ in cells
        )
        + "</clipPath>",
        "</defs>",
    ]
    timing = (
        f'keyTimes="0;{frac:.3f};1" dur="{SWEEP_EVERY}s" begin="{begin + 0.4:.2f}s" repeatCount="indefinite"'
    )
    x0, x1 = grid_x - band, grid_x + grid_w + 4
    out.append(
        f'<rect clip-path="url(#cells)" x="0" y="{grid_y}" width="{band}" height="{grid_h:.1f}" fill="url(#sweep)">'
        f'<animate attributeName="x" values="{x0:.1f};{x1:.1f};{x1:.1f}" {timing}/></rect>'
    )
    out.append(
        f'<rect x="0" y="{grid_y - 4}" width="1.5" height="{grid_h + 8:.1f}" fill="{ACCENT}" opacity=".8">'
        f'<animate attributeName="x" values="{x0 + band:.1f};{x1 + band:.1f};{x1 + band:.1f}" {timing}/>'
        f'<animate attributeName="opacity" values=".8;.8;0" keyTimes="0;{frac:.3f};{frac + .001:.3f}" '
        f'calcMode="discrete" dur="{SWEEP_EVERY}s" begin="{begin + 0.4:.2f}s" repeatCount="indefinite"/></rect>'
    )

    # Today's cell: an expanding ring that fades out, on repeat.
    c, r = cells[-1][0], cells[-1][1]
    cx = grid_x + c * pitch + size / 2
    cy = grid_y + r * pitch + size / 2
    s0, s1 = size + 2, size + 10
    out.append(
        f'<rect x="{cx - s0 / 2:.1f}" y="{cy - s0 / 2:.1f}" width="{s0:.1f}" height="{s0:.1f}" rx="3.5" '
        f'fill="none" stroke="{ACCENT}" stroke-width="1.5">'
        + "".join(
            f'<animate attributeName="{a}" values="{v0:.1f};{v1:.1f}" dur="1.8s" begin="{begin:.2f}s" '
            f'repeatCount="indefinite"/>'
            for a, v0, v1 in (
                ("x", cx - s0 / 2, cx - s1 / 2), ("y", cy - s0 / 2, cy - s1 / 2),
                ("width", s0, s1), ("height", s0, s1),
            )
        )
        + f'<animate attributeName="stroke-opacity" values="1;0" dur="1.8s" begin="{begin:.2f}s" '
        f'repeatCount="indefinite"/></rect>'
    )
    return out


def build(data: dict) -> str:
    days = data["days"]
    stats = data["stats"]

    # Promote the standout level-4 days (top 5% of active-day counts) to the neon level 5.
    active = sorted(d["count"] for d in days if d["count"] > 0)
    neon = active[int(len(active) * 0.95)] if active else 1
    neon = max(neon, 1)

    # Columns are Sunday-start weeks, exactly like GitHub's calendar.
    first = date.fromisoformat(days[0]["date"])
    week0 = first - timedelta(days=(first.weekday() + 1) % 7)
    cells = []
    for d in days:
        dt = date.fromisoformat(d["date"])
        col = (dt - week0).days // 7
        row = (dt.weekday() + 1) % 7
        level = 5 if d["level"] >= 4 and d["count"] >= neon else d["level"]
        cells.append((col, row, level, d))
    ncols = max(c[0] for c in cells) + 1

    pitch = (W - 2 * PAD - LABEL_W + GAP) / ncols
    size = pitch - GAP
    grid_x = PAD + LABEL_W
    grid_y = TOP
    h = round(grid_y + 7 * pitch - GAP + FOOT + PAD - 6)

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}">',
        "<style>",
        "text{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace;"
        f"font-size:11px;fill:{MUTED}}}",
        f".h{{font-size:13px;fill:{FG}}} .a{{fill:{ACCENT};font-weight:700}}",
    ]
    if not STATIC:
        out += [
            ".c{opacity:0;animation:drop .45s cubic-bezier(.2,.8,.3,1) forwards}",
            "@keyframes drop{from{opacity:0;transform:translateY(-7px)}to{opacity:1;transform:none}}",
            ".f{opacity:0;animation:fade .6s ease-out forwards}",
            "@keyframes fade{to{opacity:1}}",
        ]
    out += [
        "</style>",
        f'<rect x=".5" y=".5" width="{W - 1}" height="{h - 1}" rx="10" fill="{BG}" stroke="{BORDER}"/>',
    ]

    # Header: the yearly total (streaks and the rest live in stats-card.svg).
    total = f"{stats['total']:,}"
    out.append(
        f'<text x="{PAD}" y="{PAD + 6}" class="h"><tspan class="a">{total}</tspan> '
        f"contributions in the last year</text>"
    )

    # Month labels at the first column whose week contains the 1st..7th of a month.
    last_label_col = -10
    for col in range(ncols):
        wk = week0 + timedelta(weeks=col)
        for k in range(7):
            dd = wk + timedelta(days=k)
            if dd.day == 1 and col - last_label_col >= 3:
                out.append(f'<text x="{grid_x + col * pitch:.1f}" y="{grid_y - 8}">{MONTHS[dd.month - 1]}</text>')
                last_label_col = col
    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        out.append(f'<text x="{PAD}" y="{grid_y + row * pitch + size - 2:.1f}">{name}</text>')

    for col, row, level, d in cells:
        x = grid_x + col * pitch
        y = grid_y + row * pitch
        style = "" if STATIC else f' style="animation-delay:{START + (col + row) * CELL_DELAY:.3f}s"'
        out.append(
            f'<rect class="c"{style} x="{x:.1f}" y="{y:.1f}" width="{size:.1f}" height="{size:.1f}" '
            f'rx="2.5" fill="{PALETTE[level]}"><title>{d["count"]} on {d["date"]}</title></rect>'
        )

    end = START + (ncols + 7) * CELL_DELAY
    if not STATIC:
        out += radar(cells, grid_x, grid_y, pitch, size, ncols, end)

    # Footer: last-updated on the left, Less -> More legend on the right.
    fy = grid_y + 7 * pitch - GAP + 26
    fstyle = "" if STATIC else f' class="f" style="animation-delay:{end:.2f}s"'
    out.append(f"<g{fstyle}>")
    out.append(f'<text x="{grid_x}" y="{fy}">updated {data["fetched_at"][:10]} · github.com/{data["user"]}</text>')
    lx = W - PAD - 30 - len(PALETTE) * (size + GAP)
    out.append(f'<text x="{lx - 8:.1f}" y="{fy}" text-anchor="end">Less</text>')
    for i, c in enumerate(PALETTE):
        out.append(
            f'<rect x="{lx + i * (size + GAP):.1f}" y="{fy - size + 2:.1f}" width="{size:.1f}" '
            f'height="{size:.1f}" rx="2.5" fill="{c}"/>'
        )
    out.append(f'<text x="{W - PAD - 26:.1f}" y="{fy}">More</text>')
    out.append("</g>")

    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    OUT.write_text(build(data), encoding="utf-8")
    print(f"wrote {OUT.name}")


if __name__ == "__main__":
    main()
