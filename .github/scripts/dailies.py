#!/usr/bin/env python3
"""Render the last year of contributions as a film contact sheet.

Uses the GitHub GraphQL API. Set GH_TOKEN or GITHUB_TOKEN, and optionally
GH_LOGIN (defaults to pSJLq). Stdlib only, so Actions does not need a
package install.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets"

# Same amber grade as the title sequence.
DARK = ("#2a241e", "#6b4d30", "#c4843a", "#f0a646", "#f7e6c8")
LIGHT = ("#e5dcd0", "#f0d0a4", "#e09a42", "#c56e12", "#6a3814")
PLAY_DARK = "#f0a646"
PLAY_LIGHT = "#c56e12"

CELL = 14
GAP = 4
PAD_X = 5
PAD_TOP = 14
PAD_BOT = 10

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks {
          contributionDays { contributionCount weekday }
        }
      }
    }
  }
}
"""


def level(count: int, positive: list[int]) -> int:
    if count <= 0 or not positive:
        return 0
    rank = sum(1 for value in positive if value < count) / len(positive)
    if rank < 0.25:
        return 1
    if rank < 0.50:
        return 2
    if rank < 0.75:
        return 3
    return 4


def fetch(login: str, token: str) -> list[dict]:
    payload = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "User-Agent": "pSJLq-dailies",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.load(response)
    if body.get("errors"):
        raise SystemExit("GitHub GraphQL returned an error while reading the contribution calendar.")
    user = (body.get("data") or {}).get("user")
    if not user:
        raise SystemExit(f"No public contribution calendar for {login}.")
    weeks = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    if not weeks:
        raise SystemExit("Contribution calendar was empty.")
    return weeks


def sheet(weeks: list[dict], colors: tuple[str, ...], play: str) -> str:
    columns = len(weeks)
    width = PAD_X * 2 + columns * CELL + max(columns - 1, 0) * GAP
    counts = [
        day["contributionCount"]
        for week in weeks
        for day in week["contributionDays"]
        if day["contributionCount"] > 0
    ]
    positive = sorted(counts)
    height = PAD_TOP + 7 * CELL + 6 * GAP + PAD_BOT
    grid_bottom = PAD_TOP + 7 * CELL + 6 * GAP
    cells = []
    for index, week in enumerate(weeks):
        x = PAD_X + index * (CELL + GAP)
        for day in week["contributionDays"]:
            row = int(day["weekday"])
            y = PAD_TOP + row * (CELL + GAP)
            fill = colors[level(int(day["contributionCount"]), positive)]
            cells.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2.5" fill="{fill}"/>'
            )
    last = max(columns - 1, 0)
    x0 = PAD_X + CELL / 2
    x1 = PAD_X + last * (CELL + GAP) + CELL / 2
    body = f'''
<rect width="{width}" height="{height}" fill="none"/>
{''.join(cells)}
<g transform="translate({x1:.1f},0)">
  <animateTransform attributeName="transform" type="translate" values="{x0:.1f} 0; {x1:.1f} 0" dur="18s" repeatCount="indefinite"/>
  <line x1="0" y1="11" x2="0" y2="{grid_bottom}" stroke="{play}" stroke-width="8" opacity="0.16" stroke-linecap="round"/>
  <line x1="0" y1="10" x2="0" y2="{grid_bottom}" stroke="{play}" stroke-width="1.5"/>
  <polygon points="-5,1 5,1 0,8" fill="{play}"/>
</g>
'''
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-labelledby="t d">
<title id="t">Dailies</title>
<desc id="d">The last year of GitHub contributions, drawn as a film contact sheet. A playhead travels across the frames.</desc>
<style>
@media (prefers-reduced-motion: reduce) {{
  animate, animateTransform {{ display: none !important; }}
}}
</style>
{body}
</svg>
'''


def main() -> None:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("Set GH_TOKEN or GITHUB_TOKEN.")
    login = os.environ.get("GH_LOGIN") or "pSJLq"
    weeks = fetch(login, token)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, colors, play in (
        ("dailies-dark.svg", DARK, PLAY_DARK),
        ("dailies-light.svg", LIGHT, PLAY_LIGHT),
    ):
        path = OUT / name
        tmp = path.with_suffix(".svg.tmp")
        tmp.write_text(sheet(weeks, colors, play), encoding="utf-8")
        tmp.replace(path)
    print(f"Rendered {len(weeks)} weeks for {login}.")


if __name__ == "__main__":
    main()
