"""Draws the sign-in wallpaper: an illustrated vegetable market stall. Original artwork, no photo.

python3 docs/images/make_login_bg.py frontend/pwa/public/login-bg.svg
"""

import math
import random
import sys

W, H = 1600, 1000
rnd = random.Random(7)
out: list[str] = []


def add(s: str) -> None:
    out.append(s)


def tomato(x, y, r, shade):
    add(
        f'<g transform="translate({x:.0f},{y:.0f})"><circle r="{r}" fill="url(#tom{shade})"/>'
        f'<ellipse cx="{-r * 0.3:.0f}" cy="{-r * 0.35:.0f}" rx="{r * 0.28:.0f}" ry="{r * 0.16:.0f}" fill="#fff" opacity=".35"/>'
        f'<path d="M0 {-r * 0.95:.0f} l{r * 0.25:.0f} {r * 0.18:.0f} l{-r * 0.25:.0f} {r * 0.05:.0f} l{-r * 0.25:.0f} {-r * 0.05:.0f}z" fill="#2e7d32"/></g>'
    )


def orange(x, y, r):
    add(
        f'<g transform="translate({x:.0f},{y:.0f})"><circle r="{r}" fill="url(#org)"/>'
        f'<ellipse cx="{-r * 0.3:.0f}" cy="{-r * 0.35:.0f}" rx="{r * 0.25:.0f}" ry="{r * 0.14:.0f}" fill="#fff" opacity=".3"/></g>'
    )


def pepper(x, y, r):
    add(
        f'<g transform="translate({x:.0f},{y:.0f}) rotate({rnd.randint(-20, 20)})">'
        f'<path d="M{-r} 0 C{-r} {-r * 1.1:.0f} {r} {-r * 1.1:.0f} {r} 0 C{r} {r * 1.1:.0f} {r * 0.4:.0f} {r * 1.2:.0f} 0 {r * 1.2:.0f} C{-r * 0.4:.0f} {r * 1.2:.0f} {-r} {r * 1.1:.0f} {-r} 0z" fill="url(#grn)"/>'
        f'<rect x="-3" y="{-r * 1.25:.0f}" width="6" height="{r * 0.4:.0f}" rx="3" fill="#33691e"/></g>'
    )


def cauli(x, y, r, color):
    add(f'<g transform="translate({x:.0f},{y:.0f})">')
    for _ in range(14):
        a = rnd.uniform(0, 6.28)
        d = rnd.uniform(0, r * 0.6)
        add(
            f'<circle cx="{math.cos(a) * d:.0f}" cy="{math.sin(a) * d:.0f}" r="{r * rnd.uniform(0.28, 0.42):.0f}" fill="{color}"/>'
        )
    add("</g>")


def grapes(x, y, r):
    add(f'<g transform="translate({x:.0f},{y:.0f})">')
    for row in range(5):
        for k in range(5 - row):
            add(
                f'<circle cx="{(k - (4 - row) / 2) * r * 0.95:.0f}" cy="{row * r * 0.85:.0f}" r="{r * 0.5:.0f}" fill="#9ccc65" stroke="#7cb342" stroke-width="1.5"/>'
            )
    add("</g>")


def carrot(x, y, L):
    a = rnd.randint(-25, 25)
    add(
        f'<g transform="translate({x:.0f},{y:.0f}) rotate({a})"><path d="M-9 0 L9 0 L0 {L}z" fill="url(#car)"/>'
        f'<path d="M-6 -2 l-5 -16 M0 -2 l0 -20 M6 -2 l5 -16" stroke="#43a047" stroke-width="5" stroke-linecap="round"/></g>'
    )


def eggplant(x, y, r):
    add(
        f'<g transform="translate({x:.0f},{y:.0f}) rotate({rnd.randint(-30, 30)})"><ellipse rx="{r * 0.7:.0f}" ry="{r * 1.2:.0f}" fill="url(#egg)"/>'
        f'<path d="M{-r * 0.4:.0f} {-r * 1.15:.0f} q{r * 0.4:.0f} {-r * 0.35:.0f} {r * 0.8:.0f} 0" stroke="#33691e" stroke-width="8" fill="none" stroke-linecap="round"/></g>'
    )


def cabbage(x, y, r):
    add(
        f'<g transform="translate({x:.0f},{y:.0f})"><circle r="{r}" fill="#8e3b6e"/><circle r="{r * 0.7:.0f}" fill="#a64d83"/>'
        f'<path d="M{-r * 0.5:.0f} {-r * 0.5:.0f} Q0 {-r * 0.1:.0f} {r * 0.5:.0f} {-r * 0.5:.0f}M{-r * 0.6:.0f} 0 Q0 {r * 0.3:.0f} {r * 0.6:.0f} 0" stroke="#d7a3c4" stroke-width="3" fill="none"/></g>'
    )


def lights():
    for _ in range(34):
        x, y = rnd.uniform(0, W), rnd.uniform(0, H * 0.38)
        r = rnd.uniform(14, 46)
        c = rnd.choice(["#ffe082", "#ffcc80", "#fff59d", "#ffab91", "#ffffff"])
        add(
            f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.0f}" fill="{c}" opacity="{rnd.uniform(0.25, 0.6):.2f}"/>'
        )


add(
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid slice">'
)
add("""<defs>
<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2b1b12"/><stop offset=".55" stop-color="#5b3a22"/><stop offset="1" stop-color="#8a5a2b"/></linearGradient>
<radialGradient id="tomA" cx=".35" cy=".3" r=".9"><stop offset="0" stop-color="#ff6f5e"/><stop offset="1" stop-color="#c62828"/></radialGradient>
<radialGradient id="tomB" cx=".35" cy=".3" r=".9"><stop offset="0" stop-color="#ff8a65"/><stop offset="1" stop-color="#d84315"/></radialGradient>
<radialGradient id="org" cx=".35" cy=".3" r=".9"><stop offset="0" stop-color="#ffcc66"/><stop offset="1" stop-color="#ef8a00"/></radialGradient>
<radialGradient id="grn" cx=".4" cy=".3" r=".9"><stop offset="0" stop-color="#9ccc65"/><stop offset="1" stop-color="#2e7d32"/></radialGradient>
<linearGradient id="car" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ff9a2e"/><stop offset="1" stop-color="#e65100"/></linearGradient>
<radialGradient id="egg" cx=".35" cy=".3" r=".9"><stop offset="0" stop-color="#8e5bb5"/><stop offset="1" stop-color="#3b1d5a"/></radialGradient>
<filter id="soft"><feGaussianBlur stdDeviation="7"/></filter>
<filter id="softer"><feGaussianBlur stdDeviation="16"/></filter>
</defs>""")
add(f'<rect width="{W}" height="{H}" fill="url(#sky)"/>')
add('<g filter="url(#softer)">')
lights()
add("</g>")


def row(y, scale, blur, kinds):
    if blur:
        add(f'<g filter="url(#{blur})">')
    x = rnd.uniform(-20, 40)
    while x < W + 60:
        k = rnd.choice(kinds)
        r = rnd.uniform(26, 40) * scale
        if k == "tom":
            tomato(x, y, r, rnd.choice("AB"))
        elif k == "org":
            orange(x, y, r)
        elif k == "pep":
            pepper(x, y, r * 0.9)
        elif k == "cau":
            cauli(x, y, r * 1.5, rnd.choice(["#f4f1de", "#8e6bbf", "#9ccc65"]))
        elif k == "gra":
            grapes(x, y - r * 0.6, r * 0.8)
        elif k == "car":
            carrot(x, y - r, r * 2.6)
        elif k == "egg":
            eggplant(x, y, r)
        elif k == "cab":
            cabbage(x, y, r * 1.15)
        x += r * rnd.uniform(1.5, 2.1)
    if blur:
        add("</g>")


row(470, 0.8, "softer", ["org", "gra", "tom", "pep"])
row(560, 0.95, "soft", ["tom", "org", "pep", "gra", "cau"])
# stall edge with price tags
add(f'<rect y="610" width="{W}" height="40" fill="#6d4c2f" opacity=".85"/>')
row(700, 1.15, None, ["tom", "cau", "pep", "cab", "car", "egg", "tom", "org"])
row(830, 1.35, None, ["pep", "tom", "cau", "car", "cab", "egg", "tom", "pep"])
row(950, 1.5, None, ["car", "pep", "tom", "cab", "egg", "cau", "tom"])
for _ in range(9):
    x = rnd.uniform(40, W - 120)
    add(
        f'<g transform="translate({x:.0f},{rnd.randint(640, 700)}) rotate({rnd.randint(-8, 8)})"><rect width="64" height="44" rx="4" fill="#fffdf5"/><path d="M10 14h44M10 26h30" stroke="#8a7a5a" stroke-width="3" stroke-linecap="round"/></g>'
    )
add("</svg>")
open(sys.argv[1], "w").write("".join(out))
