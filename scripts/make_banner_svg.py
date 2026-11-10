"""Banner: an ASCII flyover. A camera glides down a valley between two ridgelines drawn in
shaded characters, with the name in the sky and the tagline typed out underneath.

The terrain is a heightfield that repeats along the direction of travel; the camera moves
exactly one repeat per loop, so the last frame runs into the first. Each screen column is
ray-marched near to far and filled upward as taller ground appears (the "voxel space"
trick), which gives solid hills with correct occlusion. Every frame is pre-rendered as
text and the frames are flipped through with one CSS keyframe.

Usage: python scripts/make_banner_svg.py            # writes banner.svg
       STATIC=1 python scripts/make_banner_svg.py   # frozen frame, no animation
       PREVIEW=1 python scripts/make_banner_svg.py  # print frame 0 as text, write nothing
"""
import math
import os
import random
from pathlib import Path

from theme import ACCENT, BG, FG, FG_BRIGHT, FONT, MUTED, PAD, PALETTE, W, frame

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "banner.svg"

NAME = "MUSTAFA KAMRAN"
TAGLINE = "Fullstack Developer · AI Engineer · Cloud Architect"

# Character grid of the scene.
COLS, ROWS = 150, 28
CELL_W, CELL_H = 5.4, 7.0  # rows overlap a little, so strokes join up
SCENE_FONT = 9
SCENE_X = (W - COLS * CELL_W) / 2
SCENE_Y = 18

# Loop.
FRAMES = 48
FPS = 12

# Camera and world. World units are arbitrary; z runs away from the viewer.
PERIOD = 12.0  # the heightfield repeats every PERIOD along z
GRID_Z = 0.75  # spacing of the mesh lines you fly over (must divide PERIOD)
GRID_X = 0.6  # spacing of the floor lines running into the distance
FLOOR = 1.2  # half-width of the flat valley floor
CAM_H = 0.5
HORIZON = 11.0  # screen row of the horizon
FOV = 1.1  # half-width of the view in world units at z = 1
VSCALE = 31.0  # rows per unit of height at z = 1
Z_FAR = 12.0

FOG = (2.2, 4.0, 7.0)  # depth where the colour band steps down
BANDS = [PALETTE[2], PALETTE[3], PALETTE[4], PALETTE[5]]  # far -> near

# Caption.
CAP_FONT = 13
CAP_CW = 7.8
TYPE_CPS = 24

STATIC = os.environ.get("STATIC") == "1"
PREVIEW = os.environ.get("PREVIEW") == "1"
STILL = int(os.environ.get("AT", "0"))  # which frame STATIC and PREVIEW show
TAU = math.tau


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def height(x: float, z: float) -> float:
    """Ground height. Flat down the middle, peaks on both sides, periodic in z."""
    a = abs(x)
    if a <= FLOOR:
        return 0.0
    t = min((a - FLOOR) / 1.3, 1.0)
    walls = t * t * (3 - 2 * t)
    p = z * TAU / PERIOD
    # Two sets of diagonal crests; the tallest peaks stand where they cross.
    r1 = 1 - abs(math.sin(0.62 * x + 2 * p + 0.3 + 0.5 * math.sin(p + x)))
    r2 = 1 - abs(math.sin(0.95 * x - 3 * p + 1.7))
    r3 = 1 - abs(math.sin(2.3 * x + 5 * p + 0.2))
    peaks = 0.3 + 0.45 * r1 * r1 + 0.95 * r1 * r2 + 0.2 * r3
    # Foothills beside the valley, full height further out: keeps the far centre low.
    return walls * peaks * (0.75 + 0.75 * min(a / 5.0, 1.0))


def band_for(z: float) -> int:
    return 3 if z < FOG[0] else 2 if z < FOG[1] else 1 if z < FOG[2] else 0


def floor_cell(r: int, c: int, sx: float) -> str:
    """Character for the floor lines that run into the distance, or a space."""
    half = FOV / COLS
    hits = []
    for k in range(2):
        ya, yb = r + k / 2 - HORIZON, r + (k + 1) / 2 - HORIZON
        za, zb = CAM_H * VSCALE / ya, CAM_H * VSCALE / yb
        xs = ((sx - half) * za, (sx + half) * za, (sx - half) * zb, (sx + half) * zb)
        if math.floor(min(xs) / GRID_X) != math.floor(max(xs) / GRID_X):
            hits.append(k)
    if not hits:
        return " "
    lean = abs(c + 0.5 - COLS / 2) / (r + 0.5 - HORIZON)  # columns per row
    if len(hits) > 1 and lean < 1.6:
        return "|" if lean < 0.35 else "/" if sx < 0 else "\\"
    return "-_"[hits[-1]]


def project(x: float, z_rel: float, cam_z: float) -> float:
    return HORIZON + (CAM_H - height(x, cam_z + z_rel)) / z_rel * VSCALE


def render(cam_z: float) -> tuple[list[list[str]], list[list[int]], list[int]]:
    """One frame: characters, colour band per cell, and the skyline row per column."""
    chars = [[" "] * COLS for _ in range(ROWS)]
    bands = [[0] * COLS for _ in range(ROWS)]

    # Pass 1, per column: march away from the camera tracking the highest ground seen so
    # far. A mesh line is visible in this column only if it rises above everything nearer.
    slices: dict[int, list] = {}  # mesh line index -> per column (y, limit) or None
    sky_y = [0.0] * COLS
    sky_z = [0.0] * COLS
    for c in range(COLS):
        sx = ((c + 0.5) / COLS * 2 - 1) * FOV
        ybuf, zbuf = ROWS + 2.0, 0.0
        z = 0.3
        m_prev = math.floor((cam_z + z) / GRID_Z + 1e-9)
        while z < Z_FAR:
            zn = z + max(0.01, z * 0.012)
            m = math.floor((cam_z + zn) / GRID_Z + 1e-9)
            if m != m_prev:
                zs = m * GRID_Z - cam_z
                lod = 1 if zs < 4.5 else 2 if zs < 8 else 4
                y = project(sx * zs, zs, cam_z)
                if m % lod == 0 and y < ybuf:
                    slices.setdefault(m, [None] * COLS)[c] = (y, ybuf)
                if y < ybuf:
                    ybuf, zbuf = y, zs
                m_prev = m
            y = project(sx * zn, zn, cam_z)
            if y < ybuf:
                ybuf, zbuf = y, zn
            z = zn
        sky_y[c], sky_z[c] = ybuf, zbuf

    def put(r: int, c: int, ch: str, band: int) -> None:
        if 0 <= r < ROWS:
            chars[r][c] = ch
            bands[r][c] = min(band, len(BANDS) - 1)

    def stroke(c: int, y: float, left, right, limit: float, band: int) -> None:
        """Draw one column of a line, picking the character from its local slope."""
        if left is None and right is None:
            slope = 0.0
        elif left is None:
            slope = right - y
        elif right is None:
            slope = y - left
        else:
            slope = (right - left) / 2
        r = math.floor(y)
        if abs(slope) < 0.6:
            put(r, c, "-" if y - r < 0.55 else "_", band)
        elif abs(slope) < 1.5:
            put(r, c, "/" if slope < 0 else "\\", band)
        else:
            lo = math.floor(y - abs(slope) / 2 + 0.5)
            hi = math.floor(min(y + abs(slope) / 2, limit - 0.5))
            for rr in range(lo, max(hi, r) + 1):
                put(rr, c, "|", band)

    # Floor lines running into the distance.
    for r in range(int(HORIZON) + 1, ROWS):
        z = CAM_H * VSCALE / (r + 0.5 - HORIZON)
        for c in range(COLS):
            sx = ((c + 0.5) / COLS * 2 - 1) * FOV
            if abs(sx * z) <= FLOOR + GRID_X / 2 and r + 1 <= sky_y[c] + 30:
                ch = floor_cell(r, c, sx)
                if ch != " ":
                    put(r, c, ch, max(band_for(z) - 1, 0))

    # Pass 2: draw the mesh lines far to near, so nearer strokes win a shared cell.
    for m in sorted(slices, reverse=True):
        line = slices[m]
        band = band_for(m * GRID_Z - cam_z)
        for c, pt in enumerate(line):
            if pt is None:
                continue
            left = line[c - 1][0] if c > 0 and line[c - 1] else None
            right = line[c + 1][0] if c + 1 < COLS and line[c + 1] else None
            stroke(c, pt[0], left, right, pt[1], band)

    # The skyline, one step brighter, so the ridges have a clean outline against the sky.
    for c in range(COLS):
        left = sky_y[c - 1] if c > 0 else None
        right = sky_y[c + 1] if c + 1 < COLS else None
        stroke(c, sky_y[c], left, right, ROWS, band_for(sky_z[c]) + 1)

    skyline = [max(0, math.floor(y) - 1) for y in sky_y]
    return chars, bands, skyline


def row_markup(chars: list[str], bands: list[int], y: float) -> str:
    """One row as a <text>, with a <tspan> per run of equal colour. Spaces join any run."""
    first = next((i for i, ch in enumerate(chars) if ch != " "), None)
    if first is None:
        return ""
    last = max(i for i, ch in enumerate(chars) if ch != " ")
    runs: list[tuple[int, str]] = []
    cur, buf = bands[first], ""
    for i in range(first, last + 1):
        if chars[i] != " " and bands[i] != cur:
            runs.append((cur, buf))
            cur, buf = bands[i], ""
        buf += chars[i]
    runs.append((cur, buf))
    # The row takes its most common colour; only the other runs need a <tspan>.
    weight: dict[int, int] = {}
    for b, s in runs:
        weight[b] = weight.get(b, 0) + len(s)
    main = max(weight, key=weight.get)
    body = "".join(esc(s) if b == main else f'<tspan class="c{b}">{esc(s)}</tspan>' for b, s in runs)
    n = last - first + 1
    return (
        f'<text class="c{main}" x="{SCENE_X + first * CELL_W:g}" y="{y:g}" '
        f'textLength="{n * CELL_W:g}" lengthAdjust="spacingAndGlyphs">{body}</text>'
    )


def frame_markup(chars: list[list[str]], bands: list[list[int]]) -> str:
    return "".join(
        row_markup(chars[r], bands[r], SCENE_Y + (r + 1) * CELL_H - 1.5) for r in range(ROWS)
    )


def stars(sky: list[int], keep_clear: tuple[int, int, int, int]) -> str:
    """A few static stars, only where no frame ever draws terrain."""
    rng = random.Random(7)
    c0, c1, r0, r1 = keep_clear
    out = []
    for _ in range(46):
        c, r = rng.randrange(COLS), rng.randrange(0, int(HORIZON) - 1)
        if r >= sky[c] or (c0 <= c <= c1 and r0 <= r <= r1):
            continue
        ch = rng.choice("..··++*")
        twinkle = "" if STATIC or rng.random() > 0.3 else f' class="tw" style="animation-delay:-{rng.random() * 4:.1f}s"'
        out.append(
            f'<text{twinkle} x="{SCENE_X + c * CELL_W:.1f}" y="{SCENE_Y + (r + 1) * CELL_H - 1.5:g}" '
            f'fill="{MUTED}" fill-opacity="{rng.choice((".45", ".6", ".85"))}">{ch}</text>'
        )
    return "".join(out)


def build() -> str:
    frames, sky = [], [ROWS] * COLS
    for i in range(FRAMES):
        chars, bands, skyline = render(i * PERIOD / FRAMES)
        sky = [min(a, b) for a, b in zip(sky, skyline)]
        if not STATIC or i == STILL:
            frames.append((chars, bands))

    name_cols = range(COLS // 2 - 22, COLS // 2 + 23)
    if os.environ.get("CHECK"):
        print("highest terrain row under the name:", min(sky[c] for c in name_cols))
    scene_h = ROWS * CELL_H
    cap_y = SCENE_Y + scene_h + 26
    h = round(cap_y + PAD - 4)
    loop = FRAMES / FPS
    name_y = SCENE_Y + 30

    css = [
        f"text{{font-family:{FONT};white-space:pre}}",
        f".s text{{font-size:{SCENE_FONT}px}}",
        " ".join(f".c{i}{{fill:{c}}}" for i, c in enumerate(BANDS)),
        f".n{{font-size:15px;font-weight:700;letter-spacing:7px;fill:{FG_BRIGHT};"
        f"paint-order:stroke;stroke:{BG};stroke-width:5px;stroke-linejoin:round}}",
        f".cap{{font-size:{CAP_FONT}px;fill:{FG}}} .a{{fill:{ACCENT}}}",
    ]
    if not STATIC:
        css += [
            f".f{{visibility:hidden;animation:f {loop:g}s step-end infinite}}",
            f"@keyframes f{{0%{{visibility:visible}}{100 / FRAMES:.5f}%,100%{{visibility:hidden}}}}",
            ".tw{animation:tw 4s ease-in-out infinite}",
            "@keyframes tw{0%,100%{opacity:1}50%{opacity:.2}}",
            "@media (prefers-reduced-motion:reduce){.f,.tw{animation:none}.f0{visibility:visible}}",
        ]

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}">',
        "<style>", *css, "</style>",
        frame(W, h),
        '<g class="s">',
        stars(sky, (COLS // 2 - 26, COLS // 2 + 26, 2, 6)),
    ]
    for i, (chars, bands) in enumerate(frames):
        if STATIC:
            out.append(f"<g>{frame_markup(chars, bands)}</g>")
        else:
            out.append(
                f'<g class="f f{i}" style="animation-delay:{i / FPS:.4f}s">{frame_markup(chars, bands)}</g>'
            )
    out.append("</g>")
    out.append(f'<text class="n" x="{W / 2 + 3.5:g}" y="{name_y:g}" text-anchor="middle">{NAME}</text>')

    # Tagline typed under the scene, then a blinking cursor.
    tag = f"> {TAGLINE}"
    tag_w = len(tag) * CAP_CW
    text = (
        f'<text class="cap" x="{PAD}" y="{cap_y:g}" textLength="{tag_w:g}" lengthAdjust="spacingAndGlyphs"'
        f'{{clip}}><tspan class="a">&gt;</tspan>{esc(tag[1:])}</text>'
    )
    cx = PAD + (len(tag) + 1) * CAP_CW
    cursor = f'<rect x="{cx:g}" y="{cap_y - CAP_FONT + 1:g}" width="8" height="{CAP_FONT + 2}" fill="{ACCENT}"'
    if STATIC:
        out += [text.format(clip=""), cursor + "/>"]
    else:
        t0 = 0.6
        dur = len(tag) / TYPE_CPS
        steps = ";".join(f"{k * CAP_CW:g}" for k in range(len(tag) + 1))
        out += [
            f'<clipPath id="tag"><rect x="{PAD}" y="{cap_y - CAP_FONT - 2:g}" width="0" height="21">'
            f'<animate attributeName="width" values="{steps}" calcMode="discrete" begin="{t0:g}s" '
            f'dur="{dur:.2f}s" fill="freeze"/></rect></clipPath>',
            text.format(clip=' clip-path="url(#tag)"'),
            cursor + ' opacity="0">'
            f'<set attributeName="opacity" to="1" begin="{t0 + dur:.2f}s"/>'
            '<animate attributeName="fill-opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur="1.1s" '
            f'begin="{t0:g}s" repeatCount="indefinite"/></rect>',
        ]

    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    if PREVIEW:
        chars, _, _ = render(STILL * PERIOD / FRAMES)
        print("\n".join("".join(row) for row in chars))
        return
    svg = build()
    OUT.write_text(svg, encoding="utf-8")
    print(f"wrote {OUT.name} ({len(svg) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
