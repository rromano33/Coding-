"""Shared diverging-color helpers for the HTML reports (dashboard, scenarios).

Blue/red diverging pair, gray midpoint — see the dataviz skill's palette.md.
Dark-mode steps used when the browser is in dark mode (prefers-color-scheme),
matched to each report's dark surface.
"""
from __future__ import annotations

RED_LIGHT, BLUE_LIGHT, GRAY_LIGHT = "#e34948", "#2a78d6", "#f0efec"
RED_DARK, BLUE_DARK, GRAY_DARK = "#e66767", "#3987e5", "#383835"


def lerp_hex(c1: str, c2: str, t: float) -> str:
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    r, g, b = round(r1 + (r2 - r1) * t), round(g1 + (g2 - g1) * t), round(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def diverging_color(value: float, domain: float, red: str, gray: str, blue: str) -> str:
    if domain <= 0 or value != value:  # NaN guard
        return gray
    t = max(-1.0, min(1.0, value / domain))
    return lerp_hex(gray, blue, t) if t >= 0 else lerp_hex(gray, red, -t)
