#!/usr/bin/env python3
"""Rebuild the profile title-sequence SVGs.

    python assets/generate_reel.py

Paths are converted from the OFL Instrument families in assets/fonts so the
posters render without network fonts, JavaScript, or third-party images.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parent
FONTS = ROOT / "fonts"

# Warm cinema grade. Dark is a night interior; light is a paper edit.
THEMES = {
    "dark": {
        "bg": "#12100e",
        "bar": "#0c0b0a",
        "ink": "#f4efe6",
        "muted": "#b3a89c",
        "faint": "#3a332c",
        "hair": "#2a251f",
        "amber": "#f0a646",
        "teal": "#8fd0c6",
        "rose": "#e08a68",
        "ivory": "#efe4d4",
        "glow": 0.20,
        "leak": 0.72,
        "ring": "#f4efe6",
        "ring_opacity": 0.92,
    },
    "light": {
        "bg": "#f6f1e8",
        "bar": "#efe8dc",
        "ink": "#1c1714",
        "muted": "#5e564e",
        "faint": "#ddd4c6",
        "hair": "#e4dccf",
        "amber": "#c56f12",
        "teal": "#1f6f68",
        "rose": "#c45b38",
        "ivory": "#4e463f",
        "glow": 0.11,
        "leak": 0.55,
        "ring": "#1c1714",
        "ring_opacity": 0.9,
    },
}

SUBTITLES = (
    "Motion designer",
    "Video editor",
    "Onchain, on Somnia",
)

# Fractions of em, applied between the two glyphs. Tuned by eye at display size.
TITLE_PAIRS = {
    ("S", "H"): -0.02,
    ("H", "I"): 0.045,
    ("I", "N"): 0.03,
    ("N", "Y"): -0.02,
}
TRACKING_EM = 0.012


class Font:
    def __init__(self, path: Path, axes: dict | None = None):
        self.tt = TTFont(path)
        if axes:
            instantiateVariableFont(self.tt, axes, inplace=True)
        self.gs = self.tt.getGlyphSet()
        self.cmap = self.tt.getBestCmap()
        self.upem = self.tt["head"].unitsPerEm
        self.hmtx = self.tt["hmtx"]

    def _name(self, ch: str) -> str | None:
        return self.cmap.get(ord(ch))

    def right_ink(self, ch: str, size: float) -> float:
        """Distance from the advance width back to the right edge of the ink."""
        name = self._name(ch)
        if name is None or "glyf" not in self.tt:
            return 0.0
        glyph = self.tt["glyf"][name]
        if getattr(glyph, "xMax", None) is None:
            return 0.0
        adv = self.hmtx[name][0]
        return (adv - glyph.xMax) * (size / self.upem)

    def advance(self, ch: str, size: float) -> float:
        name = self._name(ch)
        if name is None:
            return size * 0.33
        return self.hmtx[name][0] * (size / self.upem)

    def width(self, text: str, size: float, tracking: float = 0, pairs: dict | None = None) -> float:
        cursor = 0.0
        for i, ch in enumerate(text):
            cursor += self.advance(ch, size)
            if i == len(text) - 1:
                break
            cursor += tracking
            if pairs:
                cursor += pairs.get((ch, text[i + 1]), 0) * size
        return cursor

    def emit(self, text: str, size: float, x: float, y: float, fill: str, tracking: float = 0, pairs: dict | None = None) -> str:
        scale = size / self.upem
        cursor = x
        parts: list[str] = []
        for i, ch in enumerate(text):
            name = self._name(ch)
            if name and ch != " ":
                pen = SVGPathPen(self.gs)
                self.gs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, cursor, y)))
                d = pen.getCommands()
                if d:
                    parts.append(f'<path d="{_round_path(d)}" fill="{fill}"/>')
            cursor += self.advance(ch, size)
            if i != len(text) - 1:
                cursor += tracking
                if pairs:
                    cursor += pairs.get((ch, text[i + 1]), 0) * size
        return "".join(parts)


def _round_path(d: str) -> str:
    import re

    def repl(match: re.Match) -> str:
        value = float(match.group())
        text = f"{value:.2f}".rstrip("0").rstrip(".")
        if text in ("", "-0"):
            return "0"
        return text

    return re.sub(r"-?\d+\.\d+(?:e[+-]?\d+)?", repl, d)


def _wrap(width: int, height: int, body: str, title: str, desc: str) -> str:
    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-labelledby="t d" preserveAspectRatio="xMidYMid meet">
<title id="t">{title}</title>
<desc id="d">{desc}</desc>
<style>
@media (prefers-reduced-motion: reduce) {{
  animate, animateTransform, animateMotion {{ display: none !important; }}
}}
</style>
{body}
</svg>
'''
    ET.fromstring(svg)
    return svg


def _crops(width: int, top: int, bottom: int, color: str) -> str:
    inset = 16
    length = 12
    y1 = top + inset
    y2 = bottom - inset
    x1 = inset
    x2 = width - inset
    corners = (
        (x1, y1, 1, 1),
        (x2, y1, -1, 1),
        (x1, y2, 1, -1),
        (x2, y2, -1, -1),
    )
    parts = []
    for x, y, dx, dy in corners:
        parts.append(
            f'<path d="M {x} {y + dy * length} L {x} {y} L {x + dx * length} {y}" '
            f'fill="none" stroke="{color}" stroke-width="1" opacity="0.85"/>'
        )
    return "".join(parts)


def _reticle(cx: float, cy: float, r: float, pal: dict) -> str:
    ring = pal["ring"]
    amber = pal["amber"]
    opacity = pal["ring_opacity"]
    # Static crosshair and hairline stay put. Dashes and the hot dot orbit.
    return f'''
<g fill="none" stroke="{ring}" stroke-width="1" opacity="{opacity}">
  <circle cx="{cx}" cy="{cy}" r="{r}"/>
  <path d="M {cx} {cy - r - 8} V {cy - r + 10} M {cx} {cy + r - 10} V {cy + r + 8} M {cx - r - 8} {cy} H {cx - r + 10} M {cx + r - 10} {cy} H {cx + r + 8}"/>
  <circle cx="{cx}" cy="{cy}" r="2.2" fill="{ring}" stroke="none"/>
</g>
<g opacity="{opacity}">
  <animateTransform attributeName="transform" type="rotate" from="0 {cx} {cy}" to="360 {cx} {cy}" dur="32s" repeatCount="indefinite"/>
  <circle cx="{cx}" cy="{cy}" r="{r + 12}" fill="none" stroke="{amber}" stroke-width="1.25" stroke-linecap="round" stroke-dasharray="16 14 3 14"/>
</g>
<g transform="translate({cx}, {cy - r})">
  <circle r="3.4" fill="{amber}"/>
  <animateMotion dur="14s" repeatCount="indefinite" path="M 0 0 A {r} {r} 0 1 1 0 {2 * r:.2f} A {r} {r} 0 1 1 0 0"/>
</g>
'''


def _subtitles(italic: Font, size: float, x: float, y: float, fill: str) -> str:
    # Hard cuts. A dissolve stacks two different words and turns them into noise.
    frames = (
        ("1;0;0", "0;0.333;1"),
        ("0;1;0;0", "0;0.333;0.666;1"),
        ("0;0;1;0", "0;0.333;0.666;1"),
    )
    groups = []
    for index, line in enumerate(SUBTITLES):
        opacity = "1" if index == 0 else "0"
        values, keys = frames[index]
        groups.append(
            f'''<g opacity="{opacity}">
  <animate attributeName="opacity" dur="12s" repeatCount="indefinite" calcMode="discrete" values="{values}" keyTimes="{keys}"/>
  {italic.emit(line, size, x, y, fill)}
</g>'''
        )
    return "".join(groups)


def _timeline(x: float, y: float, h: float, pal: dict, widths: list[float], travel: float) -> str:
    gap = 8
    clips = []
    cursor = x
    colors = (pal["amber"], pal["teal"], pal["rose"], pal["ivory"], None)
    for width, color in zip(widths, colors):
        if color is None:
            clips.append(
                f'<rect x="{cursor:.1f}" y="{y:.1f}" width="{width:.1f}" height="{h:.1f}" rx="4" fill="none" stroke="{pal["muted"]}" stroke-width="1.25" stroke-dasharray="3.5 3" opacity="0.85"/>'
            )
        else:
            clips.append(
                f'<rect x="{cursor:.1f}" y="{y:.1f}" width="{width:.1f}" height="{h:.1f}" rx="4" fill="{color}"/>'
            )
        cursor += width + gap
    end = x + travel
    mid = y + h / 2
    return f'''
<line x1="{x}" y1="{mid}" x2="{end}" y2="{mid}" stroke="{pal["faint"]}" stroke-width="1"/>
{''.join(clips)}
<g opacity="1" transform="translate(16,0)">
  <animateTransform attributeName="transform" type="translate" values="16 0; {travel:.1f} 0" dur="12s" repeatCount="indefinite"/>
  <polygon points="{x - 5},{y - 9} {x + 5},{y - 9} {x},{y - 1}" fill="{pal["amber"]}"/>
  <line x1="{x}" y1="{y - 1}" x2="{x}" y2="{y + h + 6}" stroke="{pal["amber"]}" stroke-width="1.5"/>
</g>
'''


def _leak(width: int, top: int, bottom: int, pal: dict) -> str:
    cy = (top + bottom) / 2
    return f'''
<defs>
  <radialGradient id="glow" cx="28%" cy="46%" r="58%">
    <stop offset="0" stop-color="{pal["amber"]}" stop-opacity="{pal["glow"]}"/>
    <stop offset="1" stop-color="{pal["amber"]}" stop-opacity="0"/>
  </radialGradient>
  <filter id="soft" x="-40%" y="-40%" width="180%" height="180%">
    <feGaussianBlur stdDeviation="28"/>
  </filter>
  <clipPath id="picture">
    <rect x="0" y="{top}" width="{width}" height="{bottom - top}"/>
  </clipPath>
</defs>
<g clip-path="url(#picture)">
  <rect x="0" y="{top}" width="{width}" height="{bottom - top}" fill="url(#glow)"/>
  <g opacity="0" filter="url(#soft)">
    <animate attributeName="opacity" values="0;0;{pal["leak"]};{pal["leak"]};0" keyTimes="0;0.12;0.32;0.62;0.88" dur="11s" repeatCount="indefinite"/>
    <animateTransform attributeName="transform" type="translate" values="-{width * 0.35:.0f} 0; {width * 1.05:.0f} 0" dur="11s" repeatCount="indefinite" calcMode="spline" keySplines="0.37 0 0.2 1"/>
    <ellipse cx="0" cy="{cy:.1f}" rx="{width * 0.16:.1f}" ry="{ (bottom - top) * 0.42:.1f}" fill="{pal["amber"]}"/>
  </g>
</g>
'''


def _hud(sans: Font, pal: dict, width: int, size: float, y: float, left: float) -> str:
    label = "REC"
    tracking = size * 0.18
    word = "SOMNIA"
    word_w = sans.width(word, size, tracking)
    return (
        f'<circle cx="{left}" cy="{y - size * 0.32:.1f}" r="{size * 0.28:.1f}" fill="{pal["amber"]}">'
        f'<animate attributeName="opacity" values="1;0.35;1" dur="2.8s" repeatCount="indefinite"/>'
        f'</circle>'
        + sans.emit(label, size, left + size * 0.7, y, pal["muted"], tracking)
        + sans.emit(word, size, width - left - word_w, y, pal["muted"], tracking)
    )


def _poster(serif, italic, sans, pal, width, height, top, bottom, title_size, sub_size, hud_size, ring_r, clip_widths, title_max) -> str:
    """`bottom` is the y where the timeline bar begins. `title_max` is the target word width."""
    title = "SHINY"
    left = 36 if width < 700 else 52
    gap = 28 if width < 700 else 52
    # Scale the word up until it hits the target width or the reticle runs out of room.
    size = 48.0
    while size < 320:
        tracking = size * TRACKING_EM
        word_w = serif.width(title, size, tracking, TITLE_PAIRS)
        outer = ring_r + 14
        if word_w >= title_max or left + word_w + gap + ring_r + outer > width - 18:
            break
        size += 2
    # Shrink until the lockup also fits the picture vertically.
    while size > 56:
        tracking = size * TRACKING_EM
        word_w = serif.width(title, size, tracking, TITLE_PAIRS)
        cap_h = size * 0.70
        underline_gap = size * 0.11
        sub_gap = sub_size * 1.22
        block_h = cap_h + underline_gap + sub_gap + sub_size * 0.32
        outer = ring_r + 14
        fits_x = left + word_w + gap + ring_r + outer <= width - 16
        fits_y = block_h <= (bottom - top) - 28 and top + 12 + ring_r * 2 <= bottom - 12
        if fits_x and fits_y and word_w <= title_max + 8:
            break
        size -= 2
        ring_r = max(36, ring_r - 1)
    tracking = size * TRACKING_EM
    title_w = serif.width(title, size, tracking, TITLE_PAIRS)
    cap_h = size * 0.70
    underline_gap = size * 0.11
    sub_gap = sub_size * 1.22
    block_h = cap_h + underline_gap + sub_gap + sub_size * 0.32
    block_top = top + ((bottom - top) - block_h) / 2
    baseline = block_top + cap_h
    underline_y = baseline + underline_gap
    sub_y = underline_y + sub_gap
    ring_cx = left + title_w + gap + ring_r
    ring_cy = baseline - cap_h * 0.46
    if ring_cy - ring_r < top + 10:
        ring_cy = top + 10 + ring_r
    if ring_cy + ring_r > bottom - 10:
        ring_cy = bottom - 10 - ring_r
    title_size = size
    travel = width - left * 2 - 8
    clip_h = 24 if width < 700 else 28
    bar_h = height - bottom
    clip_y = bottom + (bar_h - clip_h) / 2 + 2

    parts = [
        f'<rect width="{width}" height="{height}" fill="{pal["bg"]}"/>',
        f'<rect width="{width}" height="{top}" fill="{pal["bar"]}"/>',
        f'<rect y="{bottom}" width="{width}" height="{height - bottom}" fill="{pal["bar"]}"/>',
        f'<line x1="0" y1="{top}" x2="{width}" y2="{top}" stroke="{pal["hair"]}" stroke-width="1"/>',
        f'<line x1="0" y1="{bottom}" x2="{width}" y2="{bottom}" stroke="{pal["hair"]}" stroke-width="1"/>',
        _leak(width, top, bottom, pal),
        _crops(width, top, bottom, pal["faint"]),
        _reticle(ring_cx, ring_cy, ring_r, pal),
        serif.emit(title, title_size, left, baseline, pal["ink"], tracking, TITLE_PAIRS),
        f'<line x1="{left}" y1="{underline_y:.1f}" x2="{left + title_w - serif.right_ink("Y", title_size) + title_size * 0.015:.1f}" y2="{underline_y:.1f}" stroke="{pal["teal"]}" stroke-width="1.25" opacity="0.9"/>',
        _subtitles(italic, sub_size, left, sub_y, pal["muted"]),
        _hud(sans, pal, width, hud_size, top * 0.68, left),
        _timeline(left, clip_y, clip_h, pal, clip_widths, travel),
    ]
    print(
        f"  title {title_size:.0f}px w={title_w:.0f} baseline={baseline:.0f} "
        f"ring=({ring_cx:.0f},{ring_cy:.0f}) r={ring_r}"
    )
    return "".join(parts)


def desktop(serif, italic, sans, pal) -> str:
    return _poster(
        serif, italic, sans, pal,
        width=960, height=520, top=46, bottom=424,
        title_size=160, sub_size=30, hud_size=14, ring_r=86,
        clip_widths=[148, 104, 78, 128, 88],
        title_max=520,
    )


def mobile(serif, italic, sans, pal) -> str:
    return _poster(
        serif, italic, sans, pal,
        width=440, height=430, top=40, bottom=328,
        title_size=90, sub_size=22, hud_size=15, ring_r=52,
        clip_widths=[68, 50, 38, 60, 42],
        title_max=230,
    )


def rule(pal: dict) -> str:
    width, height = 960, 22
    body = f'''
<rect width="{width}" height="{height}" fill="none"/>
<line x1="0" y1="11" x2="{width}" y2="11" stroke="{pal["faint"]}" stroke-width="1"/>
<g>
  <animateTransform attributeName="transform" type="translate" values="0 0; {width - 64} 0" dur="8s" repeatCount="indefinite"/>
  <line x1="0" y1="11" x2="56" y2="11" stroke="{pal["amber"]}" stroke-width="1.75" stroke-linecap="round"/>
</g>
'''
    return _wrap(width, height, body, "", "A playhead moving along a cut.")


def main() -> None:
    serif = Font(FONTS / "InstrumentSerif-Regular.ttf")
    italic = Font(FONTS / "InstrumentSerif-Italic.ttf")
    sans = Font(FONTS / "InstrumentSans-Variable.ttf", {"wght": 540, "wdth": 100})
    desc = "Animated title card for Shiny, a motion designer, video editor, and onchain builder on Somnia."
    for name, pal in THEMES.items():
        print(name, "desktop")
        desktop_svg = _wrap(960, 520, desktop(serif, italic, sans, pal), "Shiny", desc)
        print(name, "mobile")
        mobile_svg = _wrap(440, 430, mobile(serif, italic, sans, pal), "Shiny", desc)
        (ROOT / f"title-{name}.svg").write_text(desktop_svg, encoding="utf-8")
        (ROOT / f"title-mobile-{name}.svg").write_text(mobile_svg, encoding="utf-8")
        (ROOT / f"rule-{name}.svg").write_text(rule(pal), encoding="utf-8")
        print(f"  wrote title-{name}.svg ({len(desktop_svg)} bytes)")


if __name__ == "__main__":
    main()
