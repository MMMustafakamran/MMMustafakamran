"""Render data/contributions.json as a terminal-style stats dashboard SVG.

Six stat tiles plus a contributions-per-month bar chart, in a window the same size as
the ASCII portrait so the two sit level side by side. Tiles fade up and bars grow once;
a "live" dot keeps pulsing.

Usage: python scripts/render_stats_svg.py           # writes stats-card.svg
       STATIC=1 python scripts/render_stats_svg.py  # frozen frame, no animation
"""
import json
import os
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "contributions.json"
OUT = ROOT / "stats-card.svg"
PORTRAIT = ROOT / "ascii-portrait.svg"


BG = "#0d1117"
TILE = "#111821"
BORDER = "#30363d"
FG = "#e6edf3"
MUTED = "#8b949e"
ACCENT = "#39d353"
BAR_FILL = "#26a641"
BAR_TOP = "#69f0a0"

PAD = 20
GAP = 14
TILE_H = 112

START = 0.3
STAGGER = 0.12
STATIC = os.environ.get("STATIC") == "1"

MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"


def size() -> tuple[float, float]:
    """Same viewBox as the portrait, so equal display widths give equal heights."""
    try:
        head = PORTRAIT.read_text(encoding="utf-8")[:300]
        w, h = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', head).groups()
        return float(w), float(h)
    except (OSError, AttributeError):
        return 648.0, 814.0


def short(iso: str | None) -> str:
    if not iso:
        return "—"
    d = date.fromisoformat(iso)
    return f"{MONTHS[d.month - 1]} {d.day}"


def span(r: list) -> str:
    return f"{short(r[0])} – {short(r[1])}" if r and r[0] else "no active streak"


def build(data: dict) -> str:
    s = data["stats"]
    w, h = size()
    n_days = len(data["days"])
    active = s["active_days"]
    avg = s["total"] / active if active else 0

    tiles = [
        ("current streak", f'{s["current_streak"]}', "days", span(s.get("current_streak_range")), True),
        ("longest streak", f'{s["longest_streak"]}', "days", span(s.get("longest_streak_range")), False),
        ("contributions", f'{s["total"]:,}', "", "in the last year", False),
        ("active days", f"{active}", f"/ {n_days}", f"{active / n_days:.0%} of the year", False),
        ("best day", f'{s["best_day"]["count"]}', "", short(s["best_day"]["date"]), False),
        ("avg / active day", f"{avg:.1f}", "", "contributions", False),
    ]

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:g}" height="{h:g}" viewBox="0 0 {w:g} {h:g}">',
        "<style>",
        f"text{{font-family:{FONT};fill:{FG}}}",
        f".lbl{{font-size:14px;fill:{MUTED}}} .num{{font-size:38px;font-weight:700}}"
        f" .unit{{font-size:15px;fill:{MUTED}}} .sub{{font-size:12.5px;fill:{MUTED}}}"
        f" .ax{{font-size:12px;fill:{MUTED}}} .hot{{fill:{ACCENT}}}",
    ]
    if not STATIC:
        out += [
            ".t{opacity:0;animation:up .5s ease-out forwards}",
            "@keyframes up{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}",
            ".b{transform-box:fill-box;transform-origin:bottom;transform:scaleY(0);"
            "animation:grow .7s cubic-bezier(.2,.8,.3,1) forwards}",
            "@keyframes grow{to{transform:scaleY(1)}}",
            ".live{animation:pulse 1.6s ease-in-out infinite}",
            "@keyframes pulse{0%,100%{opacity:1}50%{opacity:.25}}",
        ]
    out += [
        "</style>",
        f'<rect x=".5" y=".5" width="{w - 1:g}" height="{h - 1:g}" rx="10" fill="{BG}" stroke="{BORDER}"/>',
    ]

    def delay(k: int) -> str:
        return "" if STATIC else f' style="animation-delay:{START + k * STAGGER:.2f}s"'

    tw = (w - 2 * PAD - GAP) / 2
    y0 = PAD
    for k, (label, num, unit, sub, hot) in enumerate(tiles):
        x = PAD + (k % 2) * (tw + GAP)
        y = y0 + (k // 2) * (TILE_H + GAP)
        num_cls = "num hot" if hot else "num"
        live = (
            f'<circle class="live" cx="{x + tw - 18:g}" cy="{y + 22:g}" r="4.5" fill="{ACCENT}"/>' if hot else ""
        )
        # Rough monospace advance for placing the unit right after the number.
        unit_x = x + 18 + len(num) * 38 * 0.6 + 8
        out.append(
            f'<g class="t"{delay(k)}>'
            f'<rect x="{x:g}" y="{y:g}" width="{tw:g}" height="{TILE_H}" rx="8" fill="{TILE}" stroke="{BORDER}"/>'
            f'<text x="{x + 18:g}" y="{y + 27:g}" class="lbl">$ {label}</text>{live}'
            f'<text x="{x + 18:g}" y="{y + 70:g}" class="{num_cls}">{num}</text>'
            + (f'<text x="{unit_x:g}" y="{y + 70:g}" class="unit">{unit}</text>' if unit else "")
            + f'<text x="{x + 18:g}" y="{y + 94:g}" class="sub">{sub}</text></g>'
        )

    # Contributions per month.
    cy = y0 + 3 * (TILE_H + GAP)
    ch = h - cy - PAD
    cw = w - 2 * PAD
    monthly = list(s["monthly"].items())
    peak = max((v for _, v in monthly), default=1) or 1
    out.append(
        f'<g class="t"{delay(len(tiles))}>'
        f'<rect x="{PAD}" y="{cy:g}" width="{cw:g}" height="{ch:g}" rx="8" fill="{TILE}" stroke="{BORDER}"/>'
        f'<text x="{PAD + 18}" y="{cy + 27:g}" class="lbl">$ contributions / month</text></g>'
    )
    plot_top = cy + 70
    plot_bot = cy + ch - 40
    slot = (cw - 36) / len(monthly)
    bw = slot * 0.62
    for i, (ym, v) in enumerate(monthly):
        bh = max((plot_bot - plot_top) * v / peak, 3 if v else 0)
        bx = PAD + 18 + i * slot + (slot - bw) / 2
        is_peak = v == peak
        anim = "" if STATIC else f' class="b" style="animation-delay:{START + (len(tiles) + 1) * STAGGER + i * 0.05:.2f}s"'
        out.append(
            f'<rect{anim} x="{bx:.1f}" y="{plot_bot - bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="2" '
            f'fill="{BAR_TOP if is_peak else BAR_FILL}"><title>{ym}: {v}</title></rect>'
        )
        if is_peak:
            out.append(
                f'<g class="t"{delay(len(tiles) + 3)}><text x="{bx + bw / 2:.1f}" y="{plot_bot - bh - 8:.1f}" '
                f'text-anchor="middle" style="font-size:12px;font-weight:700">{v:,}</text></g>'
            )
        m = MONTHS[int(ym[5:]) - 1][0]
        out.append(f'<text x="{bx + bw / 2:.1f}" y="{plot_bot + 22:.1f}" text-anchor="middle" class="ax">{m}</text>')

    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    OUT.write_text(build(data), encoding="utf-8")
    print(f"wrote {OUT.name}")


if __name__ == "__main__":
    main()
