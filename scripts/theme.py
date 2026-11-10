"""Shared look for every generated card: colours, font, width and the outer frame."""

BG = "#0d1117"
TILE = "#111821"
BORDER = "#30363d"
FG = "#c9d1d9"
FG_BRIGHT = "#e6edf3"
MUTED = "#8b949e"
ACCENT = "#39d353"

# Green ramp, none -> brightest (the last one is a neon top end for standout values).
PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]

FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"

W = 860  # full-width cards
PAD = 24
RADIUS = 10


def frame(w: float, h: float) -> str:
    """The rounded dark window every card sits in."""
    return (
        f'<rect x=".5" y=".5" width="{w - 1:g}" height="{h - 1:g}" rx="{RADIUS}" '
        f'fill="{BG}" stroke="{BORDER}"/>'
    )
