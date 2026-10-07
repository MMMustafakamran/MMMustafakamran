"""Scrape the public contribution calendar (no token needed) into data/contributions.json.

GitHub serves the same HTML fragment the profile page uses at
https://github.com/users/<username>/contributions.

Usage: python scripts/fetch_contributions.py [username]
"""
import json
import os
import re
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "contributions.json"
DEFAULT_USER = "MMMustafakamran"

COUNT_RE = re.compile(r"^([\d,]+) contributions?")


def fetch_html(user: str) -> str:
    resp = requests.get(
        f"https://github.com/users/{user}/contributions",
        headers={"User-Agent": "profile-readme-heatmap", "Accept": "text/html"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.text


def parse_days(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    counts = {}
    for tip in soup.find_all("tool-tip"):
        m = COUNT_RE.match(tip.get_text(strip=True))
        counts[tip.get("for")] = int(m.group(1).replace(",", "")) if m else 0

    days = []
    for td in soup.select("td.ContributionCalendar-day[data-date]"):
        days.append({
            "date": td["data-date"],
            "count": counts.get(td.get("id"), 0),
            "level": int(td.get("data-level", 0)),
        })
    if not days:
        raise SystemExit("No contribution cells found; GitHub's markup may have changed.")
    days.sort(key=lambda d: d["date"])
    return days


def streaks(days: list[dict]) -> tuple[dict, dict]:
    """Return (current, longest) streaks as {"days", "start", "end"}."""
    longest = {"days": 0, "start": None, "end": None}
    run_start, run = None, 0
    for d in days:
        if d["count"] > 0:
            run_start = run_start if run else d["date"]
            run += 1
            if run > longest["days"]:
                longest = {"days": run, "start": run_start, "end": d["date"]}
        else:
            run = 0
    # Current streak: an empty "today" doesn't break it (the day isn't over yet).
    tail = days[:-1] if days and days[-1]["count"] == 0 else days
    current = {"days": 0, "start": None, "end": None}
    for d in reversed(tail):
        if d["count"] == 0:
            break
        current = {"days": current["days"] + 1, "start": d["date"], "end": current["end"] or d["date"]}
    return current, longest


def main() -> None:
    user = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GH_USER", DEFAULT_USER)
    days = parse_days(fetch_html(user))

    current, longest = streaks(days)
    best = max(days, key=lambda d: d["count"])
    monthly: OrderedDict[str, int] = OrderedDict()
    for d in days:
        monthly[d["date"][:7]] = monthly.get(d["date"][:7], 0) + d["count"]

    data = {
        "user": user,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "range": {"start": days[0]["date"], "end": days[-1]["date"]},
        "stats": {
            "total": sum(d["count"] for d in days),
            "active_days": sum(1 for d in days if d["count"] > 0),
            "current_streak": current["days"],
            "current_streak_range": [current["start"], current["end"]],
            "longest_streak": longest["days"],
            "longest_streak_range": [longest["start"], longest["end"]],
            "best_day": {"date": best["date"], "count": best["count"]},
            "monthly": monthly,
        },
        "days": days,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    s = data["stats"]
    print(f"{user}: {s['total']} contributions, {len(days)} days "
          f"({days[0]['date']} -> {days[-1]['date']}), streak {current['days']}/{longest['days']}")


if __name__ == "__main__":
    main()
