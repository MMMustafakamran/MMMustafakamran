"""Fetch your most recently pushed repos and render them as `ls -la ~/projects` output.

Uses the public REST API; set GITHUB_TOKEN (the Actions token works) to avoid rate limits.

Usage: python scripts/render_projects_svg.py [username]   # writes projects.svg
       STATIC=1 python scripts/render_projects_svg.py      # frozen frame, no animation
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "projects.svg"
DATA = ROOT / "data" / "repos.json"
DEFAULT_USER = "MMMustafakamran"
USER_HOST = "mustafa@github"
COUNT = 6
HIDE = set()  # repo names to leave out

W = 860
PAD = 24
TITLE_H = 30
FONT_SIZE = 13
CW = 7.8  # forced character width at FONT_SIZE
LINE_H = 24

BG = "#0d1117"
BAR = "#161b22"
BORDER = "#30363d"
FG = "#c9d1d9"
MUTED = "#8b949e"
ACCENT = "#39d353"
DIR = "#58a6ff"
STAR = "#e3b341"
LANG_COLORS = {
    "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "Python": "#3572A5", "TeX": "#3D6117",
    "HTML": "#e34c26", "CSS": "#663399", "Jupyter Notebook": "#DA5B0B", "Go": "#00ADD8",
    "Java": "#b07219", "Rust": "#dea584", "Shell": "#89e051", "C++": "#f34b7d", "Dart": "#00B4AB",
}

TYPE_CPS = 16
STATIC = os.environ.get("STATIC") == "1"
FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"


def fetch(user: str) -> list[dict]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-readme-projects"}
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    resp = requests.get(
        f"https://api.github.com/users/{user}/repos",
        params={"per_page": 100, "sort": "pushed", "type": "owner"},
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    repos = [
        {
            "name": r["name"],
            "language": r["language"] or "",
            "stars": r["stargazers_count"],
            "pushed_at": r["pushed_at"],
            "description": r["description"] or "",
        }
        for r in resp.json()
        if not r["fork"] and not r["archived"] and r["name"].lower() != user.lower() and r["name"] not in HIDE
    ]
    return repos[:COUNT]


def ago(iso: str, now: datetime) -> str:
    days = (now - datetime.fromisoformat(iso.replace("Z", "+00:00"))).days
    if days < 1:
        return "today"
    if days < 7:
        return f"{days}d ago"
    if days < 60:
        return f"{days // 7}w ago"
    if days < 365:
        return f"{days // 30}mo ago"
    return f"{days // 365}y ago"


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def clip(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def build(repos: list[dict], now: datetime) -> str:
    rows = len(repos) + 3  # command, "total", repos, final prompt
    h = TITLE_H + PAD + rows * LINE_H + PAD - 6
    cmd = "ls -la ~/projects"
    prompt = f"{USER_HOST}:~$ "
    typed_at = 0.4
    listed_at = typed_at + len(cmd) / TYPE_CPS + 0.3

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h:g}" viewBox="0 0 {W} {h:g}">',
        "<style>",
        f"text{{font-family:{FONT};font-size:{FONT_SIZE}px;fill:{FG};white-space:pre}}",
        f".m{{fill:{MUTED}}} .a{{fill:{ACCENT}}} .d{{fill:{DIR};font-weight:700}} .s{{fill:{STAR}}}",
    ]
    if not STATIC:
        out += [
            ".ln{opacity:0;animation:in .35s ease-out forwards}",
            "@keyframes in{from{opacity:0;transform:translateX(-6px)}to{opacity:1;transform:none}}",
            ".cur{animation:blink 1.1s steps(1) infinite}",
            "@keyframes blink{50%{opacity:0}}",
        ]
    out += [
        "</style>",
        f'<rect x=".5" y=".5" width="{W - 1}" height="{h - 1:g}" rx="10" fill="{BG}" stroke="{BORDER}"/>',
        f'<path d="M.5 {TITLE_H}V10.5a10 10 0 0 1 10-10h{W - 21}a10 10 0 0 1 10 10V{TITLE_H}z" fill="{BAR}"/>',
        f'<line x1=".5" y1="{TITLE_H}" x2="{W - .5}" y2="{TITLE_H}" stroke="{BORDER}"/>',
    ]
    for i, c in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        out.append(f'<circle cx="{18 + i * 16}" cy="{TITLE_H / 2}" r="5" fill="{c}"/>')
    out.append(
        f'<text x="{W / 2}" y="{TITLE_H / 2 + 4}" text-anchor="middle" class="m" style="font-size:11px">'
        f"{USER_HOST}: ~/projects</text>"
    )

    def y_of(i: int) -> float:
        return TITLE_H + PAD + i * LINE_H + FONT_SIZE

    def fixed(text: str, x: float, cls: str = "", n: int | None = None) -> str:
        n = n or len(text)
        c = f' class="{cls}"' if cls else ""
        return f'<tspan x="{x:g}"{c}>{esc(text)}</tspan>' if text else ""

    user, host = USER_HOST.split("@")
    prompt_el = f'<tspan class="a">{user}@{host}</tspan><tspan class="m">:~$</tspan>'
    # Lock the prompt to the grid so the command starts exactly one cell after "$".
    plen = f' textLength="{len(prompt.rstrip()) * CW:g}" lengthAdjust="spacingAndGlyphs"'

    # Line 0: the command, typed out.
    px = PAD + len(prompt) * CW
    if STATIC:
        out.append(f'<text x="{PAD}" y="{y_of(0):g}"{plen}>{prompt_el}</text>')
        out.append(f'<text x="{px:g}" y="{y_of(0):g}">{esc(cmd)}</text>')
    else:
        steps = ";".join(f"{k * CW:g}" for k in range(len(cmd) + 1))
        out.append(
            f'<clipPath id="cmd"><rect x="{px:g}" y="{y_of(0) - FONT_SIZE:g}" width="0" height="{LINE_H}">'
            f'<animate attributeName="width" values="{steps}" calcMode="discrete" begin="{typed_at}s" '
            f'dur="{len(cmd) / TYPE_CPS:.2f}s" fill="freeze"/></rect></clipPath>'
        )
        out.append(f'<text x="{PAD}" y="{y_of(0):g}"{plen}>{prompt_el}</text>')
        out.append(f'<text x="{px:g}" y="{y_of(0):g}" clip-path="url(#cmd)">{esc(cmd)}</text>')

    def line(i: int, content: str) -> None:
        style = "" if STATIC else f' class="ln" style="animation-delay:{listed_at + (i - 1) * 0.12:.2f}s"'
        out.append(f'<g{style}><text y="{y_of(i):g}">{content}</text></g>')

    line(1, fixed(f"total {len(repos)}", PAD, "m"))

    # Columns: perms, stars, language, age, name, description.
    cols = [PAD, PAD + 12 * CW, PAD + 17 * CW, PAD + 32 * CW, PAD + 41 * CW, PAD + 66 * CW]
    desc_chars = int((W - PAD - cols[5]) / CW)
    for i, r in enumerate(repos, start=2):
        lang = r["language"] or "—"
        dot_x = cols[2] + 4
        dot = (
            f'</text><circle cx="{dot_x:g}" cy="{y_of(i) - 4.5:g}" r="4" '
            f'fill="{LANG_COLORS.get(lang, MUTED)}"/><text y="{y_of(i):g}">'
            if r["language"] else ""
        )
        content = (
            fixed("drwxr-xr-x", cols[0], "m")
            + f'<tspan x="{cols[1]:g}" class="s">★</tspan><tspan> {r["stars"]}</tspan>'
            + fixed(clip(lang, 13), cols[2] + 14)
            + fixed(ago(r["pushed_at"], now), cols[3], "m")
            + fixed(clip(r["name"], 24) + "/", cols[4], "d")
            + fixed(clip(r["description"], desc_chars), cols[5], "m")
        )
        line(i, content + dot)

    # Final prompt with a blinking cursor.
    last = len(repos) + 2
    cur_cls = "" if STATIC else ' class="cur"'
    style = "" if STATIC else f' class="ln" style="animation-delay:{listed_at + (last - 1) * 0.12:.2f}s"'
    out.append(
        f'<g{style}><text x="{PAD}" y="{y_of(last):g}"{plen}>{prompt_el}</text>'
        f'<rect{cur_cls} x="{px + 1:g}" y="{y_of(last) - FONT_SIZE + 1:g}" width="8" height="{FONT_SIZE + 2}" fill="{FG}"/></g>'
    )
    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    user = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GH_USER", DEFAULT_USER)
    now = datetime.now(timezone.utc)
    repos = fetch(user)
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps({"fetched_at": now.isoformat(timespec="seconds"), "repos": repos}, indent=1) + "\n",
                    encoding="utf-8")
    OUT.write_text(build(repos, now), encoding="utf-8")
    print(f"wrote {OUT.name} ({len(repos)} repos)")


if __name__ == "__main__":
    main()
